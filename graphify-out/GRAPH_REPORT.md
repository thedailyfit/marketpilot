# Graph Report - c:/Users/Pc/Desktop/marketpilot_ai  (2026-04-30)

## Corpus Check
- Large corpus: 274 files · ~145,229 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 3604 nodes · 7797 edges · 46 communities detected
- Extraction: 69% EXTRACTED · 31% INFERRED · 0% AMBIGUOUS · INFERRED: 2443 edges (avg confidence: 0.53)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 68|Community 68]]

## God Nodes (most connected - your core abstractions)
1. `EventType` - 595 edges
2. `BaseAgent` - 293 edges
3. `OptionSnapshot` - 114 edges
4. `UpstoxWebSocket` - 96 edges
5. `GreeksPortfolioTracker` - 86 edges
6. `ThetaBudgetManager` - 82 edges
7. `VegaExposureLimit` - 81 edges
8. `IVTrendEngine` - 77 edges
9. `SupervisorAgent` - 67 edges
10. `push()` - 62 edges

## Surprising Connections (you probably didn't know these)
- `Start the agent's main loop.` --uses--> `EventType`  [INFERRED]
  core\base_agent.py → core\event_bus.py
- `Return status string.` --uses--> `EventType`  [INFERRED]
  core\base_agent.py → core\event_bus.py
- `ConsensusEvolution - Dynamic Agent Weight System Adjusts Galaxy voting weights` --uses--> `EventType`  [INFERRED]
  core\intelligence\consensus_evolution.py → core\event_bus.py
- `Tracking data for an agent.` --uses--> `EventType`  [INFERRED]
  core\intelligence\consensus_evolution.py → core\event_bus.py
- `Dynamically adjusts Galaxy voting weights based on:     - Historical agent accu` --uses--> `EventType`  [INFERRED]
  core\intelligence\consensus_evolution.py → core\event_bus.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.01
Nodes (258): MarketRegime, multi_strategy_selector_func(), Multi-Strategy Selector Agent Runs all 3 strategies simultaneously and picks th, Start the strategy selector., Stop the strategy selector., Handle incoming tick data., Classify current market regime based on multiple factors., Score a strategy based on current market conditions. (+250 more)

### Community 1 - "Community 1"
Cohesion: 0.01
Nodes (512): o(), __(), _a(), aa(), ac(), add(), addToError(), Ae() (+504 more)

### Community 2 - "Community 2"
Cohesion: 0.01
Nodes (303): Ingest 1m candle and re-sample., BaseModel, Hook for startup logic (e.g., connecting to db/api)., Hook for shutdown logic (e.g., closing connections)., EventType, GreeksCalculator, Probability Density Function for Standard Normal Distribution, Cumulative Distribution Function for Standard Normal Distribution (+295 more)

### Community 3 - "Community 3"
Cohesion: 0.01
Nodes (165): LegRiskReport, LegRiskSimulator, Leg Risk Simulator Simulates execution risk (slippage/legging risk) for multi-l, Report on potential execution risks., Simulates worst-case scenarios during trade execution., Assess risk of legging into the spread.                  Scenarios:         1, OptionsIdeaGenerator, Options Idea Generator Converts Galaxy consensus signals into complete trade id (+157 more)

### Community 4 - "Community 4"
Cohesion: 0.02
Nodes (94): DecisionQuality, Decision Quality Analytics Judges the QUALITY of a decision independent of the, Analyze a completed trade.         Returns {grade, score, notes, category}, Grades trades based on Process vs Outcome matrix.          Matrix:     - Good, JournalEntry, Auto Trade Journal Records the lifecycle of every trade for analysis., Update an existing trade with EXIT details., Update qualitative analysis (Grades). (+86 more)

### Community 5 - "Community 5"
Cohesion: 0.03
Nodes (85): ConfluenceEngine, ConfluenceReport, Institutional Confluence Engine Evaluates alignments between Volume Zones and G, Report generated by the ConfluenceEngine., Scores entries based on multiple institutional data sources.          Scoring, Evaluate market confluence at current spot price., GammaEngine, GammaState (+77 more)

### Community 6 - "Community 6"
Cohesion: 0.04
Nodes (65): ABC, Candle, OrderBook, OrderBookLevel, Signal, Tick, adx(), atr() (+57 more)

### Community 7 - "Community 7"
Cohesion: 0.04
Nodes (62): Aggression, FillResult, FillSimulator, Fill Simulator Realistic option fill simulation using historical bid-ask spread, Order aggression level., Estimate total execution cost without simulating.                  Returns:, Result of fill simulation., Get fill simulation statistics. (+54 more)

### Community 8 - "Community 8"
Cohesion: 0.03
Nodes (58): EventBus, Register a callback for a specific event type., Publish an event to all subscribers., Enum, Leg, MultiLegExecutor, Multi-Leg Executor Executes complex option structures (Spreads, Iron Condors) w, Executes complex option structures.          Logic:     - Identifies "Hard Le (+50 more)

### Community 9 - "Community 9"
Cohesion: 0.04
Nodes (68): Ai(), as(), b(), Bi(), bn(), C(), ct(), d() (+60 more)

### Community 10 - "Community 10"
Cohesion: 0.04
Nodes (41): DrawdownGuard, DrawdownStatus, Drawdown Guard Hard enforcement of daily/weekly drawdown limits., Check if drawdown limits have been hit., Current drawdown status., Check if trading is allowed based on drawdown limits.                  Returns, Get current drawdown status., Manually reset drawdown guard.         Use with caution - bypasses safety limit (+33 more)

### Community 11 - "Community 11"
Cohesion: 0.04
Nodes (36): DebateMemory, DebateSnapshot, DebateMemory - Agent Reasoning Recorder Records and replays agent debates for p, Update a debate with trade outcome., Get formatted debate for UI replay., Get most recent debate snapshots., Calculate average dissent rate across all debates., Complete snapshot of an agent debate. (+28 more)

### Community 12 - "Community 12"
Cohesion: 0.04
Nodes (41): calculate_atr(), calculate_position_size(), calculate_risk_levels(), calculate_stop_loss(), calculate_take_profit(), calculate_trailing_stop(), Risk Calculator Module Provides ATR-based stop-loss, take-profit, and position, Calculate position size based on risk percentage.          Args:         acco (+33 more)

### Community 13 - "Community 13"
Cohesion: 0.05
Nodes (34): FrequencyStatus, Trade Frequency Regulator Prevents over-trading by limiting daily trades., Check current frequency status.                  Returns:             Frequen, Quick check if trading is allowed., Reset for new trading day., Get average daily trades over last N days., Load state from disk., Current frequency status. (+26 more)

### Community 14 - "Community 14"
Cohesion: 0.05
Nodes (22): FootprintAggregator, FootprintCandle, FootprintLevel, FootprintAggregator - Volumetric Candle Engine Converts tick-level trades into p, Process incoming TICK and aggregate into footprint candle., Volume data at a specific price level within a candle., Finalize and store completed candle., A single volumetric candle with price-level breakdown. (+14 more)

### Community 15 - "Community 15"
Cohesion: 0.05
Nodes (23): DampenerStatus, OptionsLossStreakDampener, Options Loss Streak Dampener Reduces position size after consecutive losses., Handle a losing trade., Handle a winning trade., Get size-adjusted quantity.                  Args:             base_quantity:, Get current dampener status., Check if trading should be paused. (+15 more)

### Community 16 - "Community 16"
Cohesion: 0.09
Nodes (17): AgentEvolution, AgentProfile, AgentEvolution - Dynamic Agent Reliability Tracking Tracks per-agent accuracy b, Record whether an agent's prediction was correct.         Updates rolling accur, Complete tracking data for an agent., Calculate composite reliability score., Check if agent should be suppressed., Get current reliability score for an agent. (+9 more)

### Community 17 - "Community 17"
Cohesion: 0.09
Nodes (25): When a trade closes, add it to training data.         This enables continuous l, features_to_array(), get_feature_names(), ML Feature Engineer Extracts features from market data for prediction model., Get list of feature names for model training., Convert feature dict to array for model input., add_training_sample(), load_model() (+17 more)

### Community 18 - "Community 18"
Cohesion: 0.1
Nodes (16): AuthManager, Authentication System User registration, login, and JWT token management., Generate a secure random token., Generate a unique user ID., Register a new user.                  Returns:             Dict with success, Login user and create session.                  Returns:             Dict wit, Validate session token and return user.                  Returns:, Logout user by invalidating session. (+8 more)

### Community 19 - "Community 19"
Cohesion: 0.1
Nodes (18): OptionChainAnalysis, OptionChainAnalyzer, OptionData, Option Chain Analyzer Fetches live option chain data from Upstox and calculates, Fetch live option chain from Upstox API.         Falls back to simulated data i, Converts Upstox OptionStrikeData list to our internal OptionData list., Generate simulated option chain for testing., Calculate Put-Call Ratio based on Open Interest. (+10 more)

### Community 20 - "Community 20"
Cohesion: 0.1
Nodes (13): AgentScore, ConsensusEvolution, ConsensusEvolution - Dynamic Agent Weight System Adjusts Galaxy voting weights, Update current regime and recalculate weights., Recalculate all agent weights based on accuracy + regime., Record an agent's prediction.         Prediction format: 'BULLISH', 'BEARISH',, Record whether an agent's prediction was correct.         Updates rolling accur, Tracking data for an agent. (+5 more)

### Community 21 - "Community 21"
Cohesion: 0.1
Nodes (14): CircuitBreakerMonitor, CircuitStatus, Circuit Breaker Awareness Handles NSE circuit breaker limits to prevent trading, Check if current time qualifies for trading halt., Circuit breaker status., Calculate when trading resumes after circuit., Determine if trading is safe based on circuit status.                  Returns, Quick check if symbol is currently halted. (+6 more)

### Community 22 - "Community 22"
Cohesion: 0.11
Nodes (14): ExpiryInfo, Weekly Expiry Calendar Manages Indian market weekly expiry schedules and expiry, Get the weekday number for expiry., Calculate next expiry date for a symbol.         Handles holiday adjustments., Get complete expiry information for a symbol., Expiry information for an index., Calculate theta decay acceleration.         Theta accelerates as options approa, Get which index expires today, if any. (+6 more)

### Community 23 - "Community 23"
Cohesion: 0.11
Nodes (15): PaperOrder, PaperPosition, PaperTrade, PaperTrader, Paper Trading Mode Realistic paper trading with slippage, delays, and spreads., Load previous paper trading state., Save paper trading state., Calculate realistic slippage based on volatility.                  Higher vola (+7 more)

### Community 24 - "Community 24"
Cohesion: 0.12
Nodes (13): IndiaVIXTracker, India VIX (Volatility Index) Integration Provides VIX-based trading filters and, Determine volatility regime from VIX value., Get trading recommendation based on VIX., Get SL multiplier based on VIX.         Higher VIX = wider stops needed., Get position size multiplier based on VIX.         Higher VIX = smaller positio, Determine if trading is advisable based on VIX., Get complete VIX analysis. (+5 more)

### Community 25 - "Community 25"
Cohesion: 0.1
Nodes (12): DailyStats, PerformanceTracker, Performance Tracker Tracks and calculates trading performance metrics., Get equity curve data for charting., Get drawdown history for charting., Get trade distribution by hour and day., Calculate performance metrics., Return default metrics when no trades. (+4 more)

### Community 26 - "Community 26"
Cohesion: 0.14
Nodes (12): DecayPoint, Project premium decay curve over remaining life.                  Args:, Single point on decay curve., Estimate optimal holding period before theta becomes destructive., Classify theta severity zone., Calculate weekend theta impact.                  Weekend theta is typically pr, Models non-linear theta decay for options.          Key insights:     - ATM o, Get comprehensive theta decay summary. (+4 more)

### Community 27 - "Community 27"
Cohesion: 0.13
Nodes (12): from_dict(), VIX History Store Persistent storage for India VIX history., Get VIX history for a time range.                  Args:             start_ti, Point-in-time VIX data., Get most recent VIX snapshot., Flush any remaining data., Persistent storage for India VIX history.          Storage: data/options/vix/{, Record a VIX snapshot.                  Args:             value: VIX value (+4 more)

### Community 28 - "Community 28"
Cohesion: 0.13
Nodes (9): TrapEngine - Stop-Loss Cluster & Trap Detection Identifies bull/bear traps, fai, Find swing highs and lows from price history., Find low-liquidity zones (price gaps in history)., Get current trap state., Detects market traps using:     - Failed breakout patterns     - Volume classi, Track price for swing detection., Analyze footprint for trap signals., TrapAlert (+1 more)

### Community 29 - "Community 29"
Cohesion: 0.15
Nodes (9): oi_directional_strategy_func(), OISignal, OI-Based Directional Strategy Follows institutional money flow using Open Inter, Calculate max pain price.         In production, this would analyze full option, Generate OI-based directional signal., OI-based strategy signal., Backtest version of the strategy., Standalone function for backtest engine. (+1 more)

### Community 30 - "Community 30"
Cohesion: 0.23
Nodes (3): ExecutionAgent, Returns the list of orders from the history file., Appends a new order to the history file.

### Community 31 - "Community 31"
Cohesion: 0.26
Nodes (6): Simple Momentum Strategy for Backtest Demonstration Uses EMA crossover + RSI co, Standalone function for backtest., Simple Momentum Strategy for testing.          Entry Logic:     - Fast EMA >, Generate trading signal., simple_momentum_func(), SimpleMomentumStrategy

### Community 32 - "Community 32"
Cohesion: 0.18
Nodes (7): get_status(), QueueHandler, Starts the trading bot., Stops the trading bot., Returns current running status and configuration., start_bot(), stop_bot()

### Community 33 - "Community 33"
Cohesion: 0.22
Nodes (7): Theta Decay Strategy (Iron Condor / Short Straddle) Sells premium and profits f, Backtest version of the strategy., Standalone function for backtest engine., Theta strategy signal., Generate theta decay signal.                  For backtesting, we simulate the, theta_decay_strategy_func(), ThetaSignal

### Community 34 - "Community 34"
Cohesion: 0.32
Nodes (1): ExecutionAgent

### Community 35 - "Community 35"
Cohesion: 0.33
Nodes (2): MarketDataAgent, Simulates incoming market data for testing the pipeline

### Community 36 - "Community 36"
Cohesion: 0.43
Nodes (1): StrategyAgent

### Community 37 - "Community 37"
Cohesion: 0.33
Nodes (2): MarketDataAgent, Simulates incoming market data for testing the pipeline

### Community 38 - "Community 38"
Cohesion: 0.43
Nodes (1): StrategyAgent

### Community 42 - "Community 42"
Cohesion: 0.5
Nodes (1): SystemConfig

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (2): grade_trade(), test_analytics()

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (2): print_status(), test_crash_logic()

### Community 45 - "Community 45"
Cohesion: 0.67
Nodes (1): Test script for Level-06 ExecutionGateway verification. Tests all gates includi

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (1): Test Upstox Official SDK with Sandbox Mode

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (1): Part 3: JavaScript + Assembly of dashboard.

### Community 68 - "Community 68"
Cohesion: 1.0
Nodes (1): Calculate max allowed vega.

## Knowledge Gaps
- **360 isolated node(s):** `Simulates incoming market data for testing the pipeline`, `Starts the trading bot.`, `Stops the trading bot.`, `Returns current running status and configuration.`, `Test script for Level-06 ExecutionGateway verification. Tests all gates includi` (+355 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 34`** (8 nodes): `execution.py`, `ExecutionAgent`, `.execute_order()`, `.__init__()`, `.initialize()`, `.place_upstox_order()`, `._process_orders()`, `.start()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (7 nodes): `market_data.py`, `MarketDataAgent`, `.__init__()`, `._mock_stream()`, `.start()`, `.stop()`, `Simulates incoming market data for testing the pipeline`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (7 nodes): `StrategyAgent`, `.__init__()`, `._process_data()`, `._send_entry_signal()`, `._send_exit_signal()`, `.start()`, `strategy.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (7 nodes): `MarketDataAgent`, `.__init__()`, `._mock_stream()`, `.start()`, `.stop()`, `market_data.py`, `Simulates incoming market data for testing the pipeline`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (7 nodes): `strategy.py`, `StrategyAgent`, `.__init__()`, `._process_data()`, `._send_entry_signal()`, `._send_exit_signal()`, `.start()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (4 nodes): `config_manager.py`, `SystemConfig`, `.__post_init__()`, `.update()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (3 nodes): `grade_trade()`, `test_analytics()`, `test_analytics.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (3 nodes): `print_status()`, `test_crash_logic()`, `test_crash_logic.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (3 nodes): `Test script for Level-06 ExecutionGateway verification. Tests all gates includi`, `test_gateway()`, `test_gateway.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (2 nodes): `Test Upstox Official SDK with Sandbox Mode`, `test_sandbox_sdk.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (2 nodes): `build_v2_part3.py`, `Part 3: JavaScript + Assembly of dashboard.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 68`** (1 nodes): `Calculate max allowed vega.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `EventType` connect `Community 2` to `Community 0`, `Community 3`, `Community 5`, `Community 6`, `Community 8`, `Community 11`, `Community 12`, `Community 14`, `Community 16`, `Community 17`, `Community 20`, `Community 28`?**
  _High betweenness centrality (0.543) - this node is a cross-community bridge._
- **Why does `next()` connect `Community 1` to `Community 0`, `Community 3`?**
  _High betweenness centrality (0.272) - this node is a cross-community bridge._
- **Why does `BaseAgent` connect `Community 0` to `Community 2`, `Community 3`, `Community 6`, `Community 12`, `Community 17`?**
  _High betweenness centrality (0.142) - this node is a cross-community bridge._
- **Are the 593 inferred relationships involving `EventType` (e.g. with `QueueHandler` and `SettingsUpdate`) actually correct?**
  _`EventType` has 593 INFERRED edges - model-reasoned connections that need verification._
- **Are the 287 inferred relationships involving `BaseAgent` (e.g. with `MarketRegime` and `StrategyScore`) actually correct?**
  _`BaseAgent` has 287 INFERRED edges - model-reasoned connections that need verification._
- **Are the 110 inferred relationships involving `OptionSnapshot` (e.g. with `Test script for OptionsIdeaGenerator + ConfluenceEngine.` and `Multi-Leg Execution Verification Tests the Strategy Builder and Leg Risk Simula`) actually correct?**
  _`OptionSnapshot` has 110 INFERRED edges - model-reasoned connections that need verification._
- **Are the 81 inferred relationships involving `UpstoxWebSocket` (e.g. with `QueueHandler` and `SettingsUpdate`) actually correct?**
  _`UpstoxWebSocket` has 81 INFERRED edges - model-reasoned connections that need verification._