"""Trade execution orchestrator — signals → risk → broker → DB."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.broker.interface import BrokerInterface, OrderSide, OrderStatus, OrderType
from app.core.logging import get_logger
from app.data.tick_buffer import MarketSnapshot, TickBuffer
from app.engine.signal_detector import SignalDetector
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
    ) -> None:
        self.broker = broker
        self.tick_buffer = tick_buffer
        self.signal_detector = signal_detector
        self.risk_manager = risk_manager
        self.db_session_factory = db_session_factory
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
        """Compute signals for all tickers, persist, and execute entries."""
        db: Session = self.db_session_factory()
        try:
            for ticker in tickers:
                feature = self.signal_detector.compute_signal(ticker)
                if feature is None:
                    continue

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
                )
                db.add(signal_record)
                db.flush()

                # Only act on BREAKOUT signals
                if feature.signal_type.value != "breakout":
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

                log.info(
                    "trade_executor.entry_executed",
                    ticker=ticker,
                    quantity=params.quantity,
                    price=order.fill_price,
                    score=feature.composite_score,
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

            db.commit()
        except Exception:
            db.rollback()
            log.exception("trade_executor.monitor_positions_error")
        finally:
            db.close()
