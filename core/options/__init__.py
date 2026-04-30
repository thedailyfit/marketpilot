# Options Reality Engine Package
# Phase-06: Foundation for options-accurate trading
# Phase-07: Strike & Expiry Intelligence
# Level-07: Options Memory (Historical Snapshots)

from .greeks import (
    black_scholes_price,
    calculate_greeks,
    implied_volatility
)
from .chain_snapshot import (
    OptionSnapshot,
    ChainSnapshotEngine,
    chain_snapshot_engine
)
from .iv_surface import (
    IVSurface,
    IVSurfaceEngine,
    iv_surface_engine
)
from .payoff import (
    PayoffScenario,
    PayoffSimulator,
    payoff_simulator
)
from .theta_curve import (
    ThetaDecayCurve,
    theta_decay_curve
)
from .strike_optimizer import (
    StrikeScore,
    StrikeOptimizer,
    strike_optimizer
)
from .expiry_evaluator import (
    ExpiryRecommendation,
    ExpiryEvaluator,
    expiry_evaluator
)
# Level-07: Options Memory
from .vix_history import (
    VIXSnapshot,
    VIXHistoryStore,
    vix_history_store
)
from .snapshot_service import (
    SnapshotService,
    snapshot_service
)
from .strategy_builder import (
    MultiLegStrategyBuilder,
    strategy_builder,
    SpreadStructure
)
from .iv_trend import IVTrendEngine, iv_trend_engine, IVTrendResult, TrendDirection

__all__ = [
    # Greeks
    'black_scholes_price', 'calculate_greeks', 'implied_volatility',
    # Chain Snapshot
    'OptionSnapshot', 'ChainSnapshotEngine', 'chain_snapshot_engine',
    # IV Surface
    'IVSurface', 'IVSurfaceEngine', 'iv_surface_engine',
    # Payoff
    'PayoffScenario', 'PayoffSimulator', 'payoff_simulator',
    # Theta
    'ThetaDecayCurve', 'theta_decay_curve',
    # Strike Optimizer (Phase-07)
    'StrikeScore', 'StrikeOptimizer', 'strike_optimizer',
    # Expiry Evaluator (Phase-07)
    'ExpiryRecommendation', 'ExpiryEvaluator', 'expiry_evaluator',
    # Level-07: Options Memory
    'VIXSnapshot', 'VIXHistoryStore', 'vix_history_store',
    'SnapshotService', 'snapshot_service',
]

