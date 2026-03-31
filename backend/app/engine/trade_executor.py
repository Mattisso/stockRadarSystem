"""Trade execution orchestrator — signals → risk → broker → DB."""
from datetime import datetime

from sqlalchemy.orm import Session

from app.broker.interface import BrokerInterface, OrderSide, OrderStatus, OrderType
from app.core.config import settings
from app.core.logging import get_logger
from app.core.metrics import (
    OPEN_POSITIONS,
    RISK_REJECTIONS,
    SIGNALS_DETECTED,
    TRADE_PNL,
    TRADES_EXECUTED,
)
from app.data.tick_buffer import MarketSnapshot, TickBuffer
from app.engine.buy_agent import BuyAgent
from app.engine.execution_state import ExecutionPhase, ManagedExecutionState
from app.engine.sell_agent import OpenPosition, SellAgent
from app.engine.signal_detector import SignalDetector
from app.engine.state_machine import StateMachine, SymbolStage
from app.models.signal import Signal
from app.models.signal import SignalType as DBSignalType
from app.models.trade import Trade, TradeStatus
from app.risk.risk_manager import RiskManager, RiskRejection

log = get_logger(__name__)


class TradeExecutor:
    """Orchestrates the full signal → risk → trade pipeline.

    Responsibilities:
    - Collect market data and push to tick buffer
    - Scan for signals and persist them
    - Submit orders through the broker when risk approves
    - Monitor open positions for stop-loss / take-profit exits
    """

    def __init__(
        self,
        broker: BrokerInterface,
        tick_buffer: TickBuffer,
        signal_detector: SignalDetector,
        risk_manager: RiskManager,
        db_session_factory,
        state_machine: StateMachine | None = None,
        cache=None,
        buy_agent: BuyAgent | None = None,
        sell_agent: SellAgent | None = None,
    ) -> None:
        self.broker = broker
        self.tick_buffer = tick_buffer
        self.signal_detector = signal_detector
        self.risk_manager = risk_manager
        self.db_session_factory = db_session_factory
        self.state_machine = state_machine
        self.cache = cache
        self.buy_agent = buy_agent or BuyAgent(broker=broker, risk_manager=risk_manager)
        self.sell_agent = sell_agent or SellAgent(broker=broker, risk_manager=risk_manager)
        self._open_positions: dict[str, OpenPosition] = {}
        self._execution_states: dict[str, ManagedExecutionState] = {}

    async def collect_market_data(self, tickers: list[str]) -> None:
        """Fetch quotes + order books and push to tick buffer.

        L1 quotes: prefer cache (Polygon-sourced) when available, fall back to broker.
        L2 order books: always from broker (IBKR).
        """
        for ticker in tickers:
            try:
                # L1: cache-first (Polygon), fallback to broker
                quote = None
                if self.cache:
                    quote = await self.cache.get_l1(ticker)
                if quote is None:
                    quote = await self.broker.get_quote(ticker)

                # L2: always from broker (IBKR)
                try:
                    order_book = await self.broker.get_order_book(ticker)
                except Exception:
                    order_book = None

                snapshot = MarketSnapshot(
                    quote=quote,
                    order_book=order_book,
                    timestamp=datetime.now(),
                )
                self.tick_buffer.push(ticker, snapshot)
            except Exception:
                log.exception("trade_executor.data_collection_error", ticker=ticker)

    async def scan_signals(self, tickers: list[str]) -> None:
        """Compute signals for all tickers, persist, and execute entries.

        When a StateMachine is attached, tickers must progress through
        Normal -> Watching -> Candidate -> L2 Confirm -> ReadyToBuy before
        a trade is considered. Without a state machine, the legacy behavior
        (immediate action on BREAKOUT score) is preserved.
        """
        db: Session = self.db_session_factory()
        try:
            for ticker in tickers:
                # --- Evaluate via state machine (or legacy) ---
                if self.state_machine is not None:
                    state = await self.state_machine.evaluate(ticker)
                    feature = state.feature_vector
                    if feature is None:
                        continue
                    stage_value = state.stage.value
                    reason_value = state.reason
                    is_actionable = state.stage == SymbolStage.READY_TO_BUY
                else:
                    feature = self.signal_detector.compute_signal(ticker)
                    if feature is None:
                        continue
                    stage_value = None
                    reason_value = None
                    is_actionable = feature.signal_type.value == "breakout"

                # Persist signal (all types for ML training data)
                db_signal_type = (
                    DBSignalType.BREAKOUT
                    if feature.signal_type.value == "breakout"
                    else DBSignalType.FALSE_BREAKOUT
                )
                signal_record = Signal(
                    ticker=feature.ticker,
                    signal_type=db_signal_type,
                    score=feature.composite_score,
                    liquidity_imbalance=feature.liquidity_imbalance,
                    spread_compression=feature.spread_compression,
                    bid_stacking=feature.bid_stacking,
                    volume_acceleration=feature.volume_acceleration,
                    order_aggression=feature.order_aggression,
                    ml_confidence=feature.ml_confidence,
                    stage=stage_value,
                    reason=reason_value,
                )
                db.add(signal_record)
                db.flush()
                SIGNALS_DETECTED.labels(signal_type=feature.signal_type.value).inc()

                # Only act on actionable signals
                if not is_actionable:
                    continue

                # Skip if already in position
                if ticker in self._open_positions:
                    continue

                latest = self.tick_buffer.get_latest(ticker)
                if latest is None:
                    continue

                result = await self.buy_agent.execute(
                    db=db,
                    signal_record=signal_record,
                    latest=latest,
                    signal_score=feature.composite_score,
                    stage=stage_value,
                )

                if isinstance(result, RiskRejection):
                    RISK_REJECTIONS.labels(reason=_classify_rejection(result.reason)).inc()
                    log.info(
                        "trade_executor.risk_rejected",
                        ticker=ticker,
                        reason=result.reason,
                    )
                    continue

                if result is None:
                    continue

                # Track for exit monitoring
                self._open_positions[ticker] = OpenPosition(
                    ticker=ticker,
                    trade_id=result.trade_id,
                    quantity=result.quantity,
                    entry_price=result.fill_price,
                    stop_loss=result.stop_loss,
                    target=result.target,
                    highest_price=result.fill_price,
                    entry_time=datetime.now(),
                )
                self._execution_states[ticker] = ManagedExecutionState(
                    ticker=ticker,
                    trade_id=result.trade_id,
                    order_id=result.order_id,
                    filled_at=datetime.now(),
                    target_order_id=result.target_order_id,
                    stop_order_id=result.stop_order_id,
                    current_stop_price=result.stop_loss,
                )
                self._execution_states[ticker].mark_managed()
                trade = db.query(Trade).filter_by(id=result.trade_id).first()
                if trade is not None:
                    trade.execution_phase = ExecutionPhase.MANAGED.value
                    trade.entry_order_id = result.order_id
                    trade.last_stop_price = result.stop_loss

                TRADES_EXECUTED.labels(side="buy").inc()
                OPEN_POSITIONS.set(len(self._open_positions))

                log.info(
                    "trade_executor.entry_executed",
                    ticker=result.ticker,
                    quantity=result.quantity,
                    price=result.fill_price,
                    score=feature.composite_score,
                    stage=stage_value,
                    trade_id=result.trade_id,
                    order_id=result.order_id,
                )

            db.commit()
        except Exception:
            db.rollback()
            log.exception("trade_executor.scan_signals_error")
        finally:
            db.close()

    async def monitor_positions(self) -> None:
        """Check open positions for sell-agent-managed exits."""
        if not self._open_positions:
            return

        db: Session = self.db_session_factory()
        try:
            tickers_to_close: list[str] = []

            for ticker, pos in self._open_positions.items():
                try:
                    latest = self.tick_buffer.get_latest(ticker)
                    if latest is None:
                        quote = await self.broker.get_quote(ticker)
                        try:
                            order_book = await self.broker.get_order_book(ticker)
                        except Exception:
                            order_book = None
                        latest = MarketSnapshot(
                            quote=quote,
                            order_book=order_book,
                            timestamp=datetime.now(),
                        )
                        self.tick_buffer.push(ticker, latest)

                    assessment = self.sell_agent.assess_exit(pos, latest)
                    pos.stop_loss = assessment.stop_loss
                    pos.highest_price = assessment.highest_price

                    state = self._execution_states.get(ticker)
                    if state is not None and hasattr(state, "update_stop_price"):
                        state.update_stop_price(pos.stop_loss)
                    if (
                        assessment.reason is None
                        and state is not None
                        and state.phase == ExecutionPhase.MANAGED
                    ):
                        await self._maybe_transition_runner(ticker, pos, state)

                    if assessment.reason is None:
                        continue

                    if state is not None:
                        state.mark_exit_pending(assessment.reason)

                    closed = await self.sell_agent.execute_exit(
                        db=db,
                        position=pos,
                        assessment=assessment,
                    )
                    if not closed:
                        continue

                    TRADES_EXECUTED.labels(side="sell").inc()
                    trade = db.query(Trade).filter_by(id=pos.trade_id).first()
                    pnl = trade.pnl if trade and trade.pnl is not None else 0.0
                    TRADE_PNL.observe(pnl)
                    tickers_to_close.append(ticker)
                    if state is not None:
                        state.mark_closed(assessment.reason)

                    log.info(
                        "trade_executor.exit_executed",
                        ticker=ticker,
                        reason=assessment.reason,
                        pnl=round(pnl, 2),
                    )
                except Exception:
                    log.exception("trade_executor.monitor_error", ticker=ticker)

            # Remove closed positions
            for ticker in tickers_to_close:
                del self._open_positions[ticker]
                self._execution_states.pop(ticker, None)
            if tickers_to_close:
                OPEN_POSITIONS.set(len(self._open_positions))

            db.commit()
        except Exception:
            db.rollback()
            log.exception("trade_executor.monitor_positions_error")
        finally:
            db.close()

    async def _maybe_transition_runner(
        self,
        ticker: str,
        position: OpenPosition,
        state: ManagedExecutionState,
    ) -> None:
        trigger_price = round(
            position.entry_price * (1.0 + settings.runner_trigger_profit_pct),
            4,
        )
        if position.highest_price < trigger_price:
            return

        try:
            await self.broker.cancel_target_leg(state.order_id)
        except NotImplementedError:
            pass

        breakeven_stop = round(position.entry_price, 4)
        try:
            await self.broker.revise_stop_leg(state.order_id, breakeven_stop)
        except NotImplementedError:
            pass

        position.stop_loss = max(position.stop_loss, breakeven_stop)
        state.mark_runner_mode()
        db: Session = self.db_session_factory()
        try:
            trade = db.query(Trade).filter_by(id=state.trade_id).first()
            if trade is not None:
                trade.runner_mode = "true"
                trade.execution_phase = ExecutionPhase.RUNNER_MODE.value
                trade.last_stop_price = position.stop_loss
                db.commit()
        except Exception:
            db.rollback()
            log.exception("trade_executor.runner_mode_persist_failed", ticker=ticker, trade_id=state.trade_id)
        finally:
            db.close()
        log.info(
            "trade_executor.runner_mode_started",
            ticker=ticker,
            trade_id=state.trade_id,
            order_id=state.order_id,
            stop_loss=position.stop_loss,
        )


def _classify_rejection(reason: str) -> str:
    """Normalize rejection reasons into stable metric labels."""
    if "Daily loss" in reason:
        return "daily_loss_limit"
    if "Max positions" in reason:
        return "max_positions"
    if "Already holding" in reason:
        return "already_holding"
    if "Invalid entry" in reason:
        return "invalid_price"
    return "other"
