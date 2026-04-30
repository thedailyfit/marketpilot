# Mode-Specific Engines Package
# Contains specialized engines for each trading mode

from .equity_engines import (
    SupportResistanceEngine, support_resistance_engine,
    TrendEngine, trend_engine,
    BreakoutEngine, breakout_engine,
    MomentumEngine, momentum_engine,
)

from .futures_engines import (
    BasisEngine, basis_engine,
    RolloverEngine, rollover_engine,
    ContangoEngine, contango_engine,
    SpreadEngine, spread_engine,
)

__all__ = [
    # Equity
    'SupportResistanceEngine', 'support_resistance_engine',
    'TrendEngine', 'trend_engine',
    'BreakoutEngine', 'breakout_engine',
    'MomentumEngine', 'momentum_engine',
    # Futures
    'BasisEngine', 'basis_engine',
    'RolloverEngine', 'rollover_engine',
    'ContangoEngine', 'contango_engine',
    'SpreadEngine', 'spread_engine',
]
