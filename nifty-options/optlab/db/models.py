"""Persistent schema (SQLAlchemy 2.x). SQLite for the prototype; the same
models run unchanged on PostgreSQL by switching the URL in config.

Research tables are APPEND-ONLY by convention: experiments and backtest runs
are never updated or deleted; a re-run creates a new run row.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# --------------------------------------------------------------------- market
class MarketTick(Base):
    __tablename__ = "market_ticks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True)
    ltp: Mapped[float] = mapped_column(Float)
    bid: Mapped[float | None] = mapped_column(Float)
    ask: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)
    oi: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32))


class UnderlyingCandle(Base):
    __tablename__ = "underlying_candles"
    __table_args__ = (UniqueConstraint("underlying", "kind", "interval_min", "ts", "data_version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    underlying: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(8))           # INDEX | FUT | VIX
    interval_min: Mapped[int] = mapped_column(Integer)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)  # bar END
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)
    data_version: Mapped[str] = mapped_column(String(64), index=True)


class Expiry(Base):
    __tablename__ = "expiries"
    __table_args__ = (UniqueConstraint("underlying", "expiry", "data_version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    underlying: Mapped[str] = mapped_column(String(16))
    expiry: Mapped[date] = mapped_column(Date, index=True)
    is_monthly: Mapped[bool] = mapped_column(Boolean)
    lot_size: Mapped[int] = mapped_column(Integer)
    data_version: Mapped[str] = mapped_column(String(64))


class OptionQuoteRow(Base):
    __tablename__ = "option_quotes"
    __table_args__ = (Index("ix_oq_lookup", "data_version", "ts", "expiry", "strike", "right"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime)
    underlying: Mapped[str] = mapped_column(String(16))
    expiry: Mapped[date] = mapped_column(Date)
    strike: Mapped[float] = mapped_column(Float)
    right: Mapped[str] = mapped_column(String(2))
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    bid: Mapped[float | None] = mapped_column(Float)
    ask: Mapped[float | None] = mapped_column(Float)
    ltp: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)
    oi: Mapped[float | None] = mapped_column(Float)
    iv: Mapped[float | None] = mapped_column(Float)
    data_version: Mapped[str] = mapped_column(String(64))


class OptionChainSnapshot(Base):
    __tablename__ = "option_chain_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    underlying: Mapped[str] = mapped_column(String(16))
    expiry: Mapped[date] = mapped_column(Date)
    spot: Mapped[float] = mapped_column(Float)
    futures: Mapped[float | None] = mapped_column(Float)
    vix: Mapped[float | None] = mapped_column(Float)
    chain: Mapped[dict] = mapped_column(JSON)  # list of rows, CHAIN_COLUMNS
    source: Mapped[str] = mapped_column(String(32))


# ------------------------------------------------------------------- research
class StrategyConfigRow(Base):
    __tablename__ = "strategy_configs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    version: Mapped[str] = mapped_column(String(32))
    config_hash: Mapped[str] = mapped_column(String(64), unique=True)
    params: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ExperimentRow(Base):
    __tablename__ = "experiments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id: Mapped[str] = mapped_column(String(16), unique=True)   # EXP-001
    title: Mapped[str] = mapped_column(String(256))
    hypothesis: Mapped[str] = mapped_column(Text)
    spec: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16))   # registered | completed
    verdict: Mapped[str | None] = mapped_column(String(32))
    summary: Mapped[dict | None] = mapped_column(JSON)
    code_version: Mapped[str] = mapped_column(String(64))
    data_version: Mapped[str] = mapped_column(String(64))
    is_synthetic: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True)
    experiment_id: Mapped[str | None] = mapped_column(String(16), index=True)
    variant: Mapped[str] = mapped_column(String(128))
    strategy_name: Mapped[str] = mapped_column(String(128))
    strategy_version: Mapped[str] = mapped_column(String(32))
    params: Mapped[dict] = mapped_column(JSON)
    code_version: Mapped[str] = mapped_column(String(64))
    data_version: Mapped[str] = mapped_column(String(64))
    is_synthetic: Mapped[bool] = mapped_column(Boolean)
    fill_model: Mapped[str] = mapped_column(String(16))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    metrics: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BacktestTradeRow(Base):
    __tablename__ = "backtest_trades"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    record: Mapped[dict] = mapped_column(JSON)   # full trade record (see backtest.engine.TradeRecord)


class SignalRow(Base):
    __tablename__ = "signals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    mode: Mapped[str] = mapped_column(String(8))         # backtest | paper
    strategy: Mapped[str] = mapped_column(String(128))
    direction: Mapped[str] = mapped_column(String(8))
    features: Mapped[dict] = mapped_column(JSON)
    acted: Mapped[bool] = mapped_column(Boolean)


class RejectedSignalRow(Base):
    __tablename__ = "rejected_signals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    mode: Mapped[str] = mapped_column(String(8))
    run_id: Mapped[str | None] = mapped_column(String(64), index=True)
    strategy: Mapped[str] = mapped_column(String(128))
    direction: Mapped[str] = mapped_column(String(8))
    stage: Mapped[str] = mapped_column(String(16))      # structure | liquidity | risk
    reasons: Mapped[list] = mapped_column(JSON)
    details: Mapped[dict] = mapped_column(JSON)


# ---------------------------------------------------------------------- paper
class PaperOrder(Base):
    __tablename__ = "paper_orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    position_id: Mapped[str] = mapped_column(String(64), index=True)
    symbol: Mapped[str] = mapped_column(String(64))
    side: Mapped[str] = mapped_column(String(4))
    units: Mapped[int] = mapped_column(Integer)
    intent: Mapped[str] = mapped_column(String(8))      # OPEN | CLOSE


class PaperFill(Base):
    __tablename__ = "paper_fills"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("paper_orders.id"))
    ts: Mapped[datetime] = mapped_column(DateTime)
    price: Mapped[float] = mapped_column(Float)
    mid: Mapped[float] = mapped_column(Float)
    bid: Mapped[float | None] = mapped_column(Float)
    ask: Mapped[float | None] = mapped_column(Float)
    ltp: Mapped[float | None] = mapped_column(Float)
    slippage_points: Mapped[float] = mapped_column(Float)
    fees: Mapped[float] = mapped_column(Float)
    spread_estimated: Mapped[bool] = mapped_column(Boolean)


class PaperPosition(Base):
    __tablename__ = "paper_positions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position_id: Mapped[str] = mapped_column(String(64), unique=True)
    strategy: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(8))      # OPEN | CLOSED
    opened_at: Mapped[datetime] = mapped_column(DateTime)
    record: Mapped[dict] = mapped_column(JSON)          # live state, marks, exit conditions


class PaperTrade(Base):
    __tablename__ = "paper_trades"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position_id: Mapped[str] = mapped_column(String(64), unique=True)
    strategy: Mapped[str] = mapped_column(String(128))
    entry_ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    exit_ts: Mapped[datetime] = mapped_column(DateTime)
    net_pnl: Mapped[float] = mapped_column(Float)
    record: Mapped[dict] = mapped_column(JSON)


class DailyMetric(Base):
    __tablename__ = "daily_metrics"
    __table_args__ = (UniqueConstraint("day", "mode", "strategy"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[date] = mapped_column(Date)
    mode: Mapped[str] = mapped_column(String(8))
    strategy: Mapped[str] = mapped_column(String(128))
    metrics: Mapped[dict] = mapped_column(JSON)


class AccountEquity(Base):
    __tablename__ = "account_equity"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    mode: Mapped[str] = mapped_column(String(8))
    equity: Mapped[float] = mapped_column(Float)
    realized: Mapped[float] = mapped_column(Float)
    unrealized: Mapped[float] = mapped_column(Float)
    open_risk: Mapped[float] = mapped_column(Float)
