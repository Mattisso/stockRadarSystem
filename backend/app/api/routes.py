"""REST API routes for Stock Radar System."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.signal import Signal
from app.models.symbol import Symbol
from app.models.trade import Trade
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
