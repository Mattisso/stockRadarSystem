"""Trade execution orchestrator — signals → risk → broker → DB."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.broker.interface import BrokerInterface, OrderSide, OrderStatus, OrderType
from app.core.logging import get_logger
from app.core.metrics import (
    OPEN_POSITIONS,
    RISK_REJECTIONS,
    SIGNALS_DETECTED,
    TRADE_PNL,
    TRADES_EXECUTED,
)
from app.data.tick_buffer import MarketSnapshot, TickBuffer
from app.engine.signal_detector import SignalDetector
from app.engine.state_machine import StateMachine, SymbolStage
from app.models.signal import Signal
from app.models.signal import SignalType as DBSignalType
from app.models.trade import Trade, TradeSide, TradeStatus
from app.risk.risk_manager import RiskManager, RiskRejection, TradeParameters

log = get_logger(__name__)


@dataclass
class OpenPosition:
    """In-memory tracking for fast exit monitoring."""

    ticker: str
    trade_id: int
    quantity: int
    entry_price: float
    stop_loss: float
    target: float


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
    ) -> None:
        self.broker = broker
        self.tick_buffer = tick_buffer
        self.signal_detector = signal_detector
        self.risk_manager = risk_manager
        self.db_session_factory = db_session_factory
        self.state_machine = state_machine
        self._open_positions: dict[str, OpenPosition] = {}

    async def collect_market_data(self, tickers: list[str]) -> None:
        """Fetch quotes + order books and push to tick buffer."""
        for ticker in tickers:
            try:
                quote = await self.broker.get_quote(ticker)
                order_book = await self.broker.get_order_book(ticker)
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

                entry_price = latest.quote.ask  # buy at ask

                # Risk evaluation
                result = await self.risk_manager.evaluate_trade(
                    ticker=ticker,
                    entry_price=entry_price,
                    signal_score=feature.composite_score,
                )

                if isinstance(result, RiskRejection):
                    RISK_REJECTIONS.labels(reason=_classify_rejection(result.reason)).inc()
                    log.info(
                        "trade_executor.risk_rejected",
                        ticker=ticker,
                        reason=result.reason,
                    )
                    continue

                # Execute entry
                params: TradeParameters = result
                order = await self.broker.submit_order(
                    ticker=params.ticker,
                    side=OrderSide.BUY,
                    quantity=params.quantity,
                    order_type=OrderType.MARKET,
                )

                if order.status != OrderStatus.FILLED:
                    log.warning(
                        "trade_executor.order_not_filled",
                        ticker=ticker,
                        status=order.status.value,
                    )
                    continue

                # Persist trade
                trade_record = Trade(
                    ticker=ticker,
                    signal_id=signal_record.id,
                    side=TradeSide.BUY,
                    status=TradeStatus.FILLED,
                    quantity=params.quantity,
                    entry_price=order.fill_price,
                    stop_loss_price=params.stop_loss_price,
                    target_price=params.target_price,
                    signal_score=feature.composite_score,
                    entry_time=datetime.now(),
                )
                db.add(trade_record)
                db.flush()

                # Mark signal as acted on
                signal_record.acted_on = True

                # Track for exit monitoring
                self._open_positions[ticker] = OpenPosition(
                    ticker=ticker,
                    trade_id=trade_record.id,
                    quantity=params.quantity,
                    entry_price=order.fill_price,
                    stop_loss=params.stop_loss_price,
                    target=params.target_price,
                )

                TRADES_EXECUTED.labels(side="buy").inc()
                OPEN_POSITIONS.set(len(self._open_positions))

                log.info(
                    "trade_executor.entry_executed",
                    ticker=ticker,
                    quantity=params.quantity,
                    price=order.fill_price,
                    score=feature.composite_score,
                    stage=stage_value,
                )

            db.commit()
        except Exception:
            db.rollback()
            log.exception("trade_executor.scan_signals_error")
        finally:
            db.close()

    async def monitor_positions(self) -> None:
        """Check open positions for stop-loss / take-profit exits."""
        if not self._open_positions:
            return

        db: Session = self.db_session_factory()
        try:
            tickers_to_close: list[str] = []

            for ticker, pos in self._open_positions.items():
                try:
                    quote = await self.broker.get_quote(ticker)
                    current_price = quote.bid  # exit at bid

                    exit_reason = self.risk_manager.check_exit_conditions(
                        position=None,  # not needed for price check
                        current_price=current_price,
                        stop_loss=pos.stop_loss,
                        target=pos.target,
                    )

                    if exit_reason is None:
                        continue

                    # Submit sell order
                    order = await self.broker.submit_order(
                        ticker=ticker,
                        side=OrderSide.SELL,
                        quantity=pos.quantity,
                        order_type=OrderType.MARKET,
                    )

                    if order.status != OrderStatus.FILLED:
                        continue

                    # Calculate P&L
                    pnl = (order.fill_price - pos.entry_price) * pos.quantity
                    self.risk_manager.record_pnl(pnl)

                    # Update trade record in DB
                    trade = db.query(Trade).filter_by(id=pos.trade_id).first()
                    if trade:
                        trade.status = TradeStatus.CLOSED
                        trade.exit_price = order.fill_price
                        trade.exit_time = datetime.now()
                        trade.pnl = pnl

                        # Backfill outcome on the originating signal
                        if trade.signal_id:
                            signal = db.query(Signal).filter_by(id=trade.signal_id).first()
                            if signal:
                                signal.outcome_pnl = pnl

                    TRADES_EXECUTED.labels(side="sell").inc()
                    TRADE_PNL.observe(pnl)
                    tickers_to_close.append(ticker)

                    log.info(
                        "trade_executor.exit_executed",
                        ticker=ticker,
                        reason=exit_reason,
                        pnl=round(pnl, 2),
                    )
                except Exception:
                    log.exception("trade_executor.monitor_error", ticker=ticker)

            # Remove closed positions
            for ticker in tickers_to_close:
                del self._open_positions[ticker]
            if tickers_to_close:
                OPEN_POSITIONS.set(len(self._open_positions))

            db.commit()
        except Exception:
            db.rollback()
            log.exception("trade_executor.monitor_positions_error")
        finally:
            db.close()


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
