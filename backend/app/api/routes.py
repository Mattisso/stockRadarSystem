"""REST API routes for Stock Radar System."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.ml.analytics import TradeAnalytics
from app.ml.backtest import BacktestConfig, SignalBacktester
from app.models.signal import Signal
from app.models.symbol import Symbol
from app.models.trade import Trade
from app.schemas.ml import (
    BacktestRequest,
    BacktestResponse,
    KPIResponse,
    MLStatusResponse,
    RetrainResponse,
)
from app.schemas.signal import SignalRead
from app.schemas.symbol import SymbolRead
from app.schemas.trade import TradeRead

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/universe", response_model=list[SymbolRead])
def get_universe(active_only: bool = True, db: Session = Depends(get_db)):
    """Get all symbols in the universe."""
    query = db.query(Symbol)
    if active_only:
        query = query.filter_by(is_active=True)
    return query.order_by(Symbol.ticker).all()


@router.get("/trades", response_model=list[TradeRead])
def get_trades(limit: int = 50, db: Session = Depends(get_db)):
    """Get recent trades."""
    return db.query(Trade).order_by(Trade.created_at.desc()).limit(limit).all()


@router.get("/signals", response_model=list[SignalRead])
def get_signals(limit: int = 50, db: Session = Depends(get_db)):
    """Get recent signals."""
    return db.query(Signal).order_by(Signal.created_at.desc()).limit(limit).all()


@router.get("/portfolio")
async def get_portfolio(request: Request):
    """Get current portfolio — delegates to the active broker instance."""
    broker = request.app.state.broker
    summary = await broker.get_account_summary()
    return asdict(summary)


# ── ML Endpoints ─────────────────────────────────────────────────────


@router.get("/ml/status", response_model=MLStatusResponse)
async def ml_status(request: Request):
    """Get ML model status and configuration."""
    classifier = getattr(request.app.state, "classifier", None)
    return MLStatusResponse(
        model_trained=classifier.is_trained if classifier else False,
        feature_importances=classifier.feature_importances() if classifier and classifier.is_trained else None,
        ml_enabled=settings.ml_enabled,
        ml_confidence_weight=settings.ml_confidence_weight,
        min_training_samples=settings.ml_min_training_samples,
    )


@router.post("/ml/retrain", response_model=RetrainResponse)
async def ml_retrain(request: Request):
    """Trigger manual model retraining."""
    trainer = getattr(request.app.state, "trainer", None)
    if trainer is None:
        return RetrainResponse(status="error")

    metrics = await trainer.retrain_if_needed()
    if metrics is None:
        return RetrainResponse(status="insufficient_data")

    return RetrainResponse(status="retrained", samples=metrics.get("samples"), metrics=metrics)


@router.post("/ml/backtest", response_model=BacktestResponse)
def ml_backtest(body: BacktestRequest, db: Session = Depends(get_db)):
    """Run a signal-replay backtest."""
    config = BacktestConfig(
        start_date=body.start_date,
        end_date=body.end_date,
        slippage_pct=body.slippage_pct,
        commission_per_share=body.commission_per_share,
        initial_capital=body.initial_capital,
        max_position_size=body.max_position_size,
        score_threshold=body.score_threshold,
    )
    result = SignalBacktester(db, config).run()
    return BacktestResponse(
        total_trades=result.total_trades,
        winning_trades=result.winning_trades,
        losing_trades=result.losing_trades,
        total_pnl=result.total_pnl,
        win_rate=result.win_rate,
        avg_win=result.avg_win,
        avg_loss=result.avg_loss,
        profit_factor=result.profit_factor,
        max_drawdown=result.max_drawdown,
        sharpe_ratio=result.sharpe_ratio,
        trades=result.trades,
    )


# ── Analytics Endpoints ──────────────────────────────────────────────


@router.get("/analytics/kpis", response_model=KPIResponse)
def analytics_kpis(days: int = 30, db: Session = Depends(get_db)):
    """Get trading KPIs for the last N days."""
    return TradeAnalytics(db).compute_kpis(days=days)


@router.get("/analytics/signal-accuracy")
def analytics_signal_accuracy(db: Session = Depends(get_db)):
    """Get win rate by signal score bucket."""
    return TradeAnalytics(db).signal_accuracy_by_bucket()
