"""
ML-Powered Prediction Engine
Replaces random win_rate with real ML model predictions.
"""
import time
from datetime import datetime
from typing import List, Dict, Optional
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType
from ml.feature_engineer import extract_features
from ml.train_model import predict_win_probability, load_model, add_training_sample


class PredictionEngine(BaseAgent):
    """
    AI-powered prediction engine using ML model.
    Predictions based on technical indicators, market regime, and time patterns.
    """
    
    def __init__(self):
        super().__init__("PredictionEngine")
        self.model = None
        self.recent_candles: Dict[str, List[dict]] = {}
        self.recent_prices: Dict[str, List[float]] = {}
        self.prediction_cache: Dict[str, dict] = {}
        self.cache_ttl = 30  # Cache predictions for 30 seconds
        
    async def on_start(self):
        # Load ML model
        self.model = load_model()
        self.logger.info(f"PredictionEngine started. Model: {type(self.model).__name__}")
        
        # Subscribe to market data to build history
        bus.subscribe(EventType.MARKET_DATA, self.on_tick)
        bus.subscribe(EventType.CANDLE_DATA, self.on_candle)
        bus.subscribe(EventType.ORDER_EXECUTION, self.on_trade_closed)
    
    async def on_stop(self):
        pass
    
    async def on_tick(self, tick: dict):
        """Store price history for predictions."""
        symbol = tick.get('symbol', 'UNKNOWN')
        price = tick.get('ltp', 0.0)
        
        if symbol not in self.recent_prices:
            self.recent_prices[symbol] = []
        
        self.recent_prices[symbol].append(price)
        self.recent_prices[symbol] = self.recent_prices[symbol][-200:]
    
    async def on_candle(self, candle: dict):
        """Store candle history."""
        symbol = candle.get('symbol', 'UNKNOWN')
        
        if symbol not in self.recent_candles:
            self.recent_candles[symbol] = []
        
        self.recent_candles[symbol].append(candle)
        self.recent_candles[symbol] = self.recent_candles[symbol][-100:]
    
    async def on_trade_closed(self, execution: dict):
        """
        When a trade closes, add it to training data.
        This enables continuous learning.
        """
        symbol = execution.get('symbol', 'UNKNOWN')
        pnl = execution.get('pnl', 0.0)
        direction = execution.get('action', 'BUY')
        
        # Only record closed trades (with known P&L)
        if pnl == 0.0:
            return
        
        # Get features at time of trade (from cache or regenerate)
        candles = self.recent_candles.get(symbol, [])
        prices = self.recent_prices.get(symbol, [])
        
        if not prices or not candles:
            return
        
        features = extract_features(
            candles=candles,
            prices=prices,
            current_volume=candles[-1].get('volume', 0) if candles else 0,
            timestamp=time.time()
        )
        
        outcome = 1 if pnl > 0 else 0
        
        add_training_sample(
            features=features,
            outcome=outcome,
            direction=direction,
            pnl=pnl
        )
        
        self.logger.info(f"Training sample recorded: {symbol} | P&L: ₹{pnl:.2f} | Outcome: {'WIN' if outcome else 'LOSS'}")
    
    def predict_success(self, strategy_id: str, symbol: str) -> dict:
        """
        Predict success probability for a potential trade.
        
        Returns:
            Dict with win_rate, confidence, time_slot_analysis, and recommendation
        """
        # Check cache
        cache_key = f"{symbol}_{strategy_id}"
        if cache_key in self.prediction_cache:
            cached = self.prediction_cache[cache_key]
            if time.time() - cached['timestamp'] < self.cache_ttl:
                return cached['prediction']
        
        # Get market data
        candles = self.recent_candles.get(symbol, [])
        prices = self.recent_prices.get(symbol, [])
        
        # Not enough data
        if len(prices) < 20:
            return self._default_prediction("INSUFFICIENT_DATA")
        
        # Get current volume
        current_volume = candles[-1].get('volume', 0) if candles else 0
        
        # ML Prediction
        win_probability = predict_win_probability(
            candles=candles,
            prices=prices,
            current_volume=current_volume,
            timestamp=time.time()
        )
        
        # Time Slot Analysis
        time_slot = self._analyze_time_slot()
        
        # Adjust probability based on time slot
        if time_slot == "TRAP_ZONE_DANGER":
            win_probability *= 0.8  # Reduce confidence
        elif time_slot == "TREND_REVERSAL_GOLD":
            win_probability *= 1.1  # Increase confidence
        
        win_probability = min(0.95, max(0.05, win_probability))  # Clamp
        
        # Determine confidence level
        if win_probability >= 0.70:
            confidence = "HIGH"
        elif win_probability >= 0.55:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"
        
        # Generate recommendation
        if win_probability >= 0.65 and time_slot != "TRAP_ZONE_DANGER":
            recommendation = "TAKE_TRADE"
        elif win_probability >= 0.55:
            recommendation = "WAIT_FOR_CONFIRMATION"
        else:
            recommendation = "SKIP"
        
        prediction = {
            "strategy": strategy_id,
            "symbol": symbol,
            "win_rate": f"{int(win_probability * 100)}%",
            "win_probability": round(win_probability, 2),
            "time_slot_analysis": time_slot,
            "confidence": confidence,
            "recommendation": recommendation,
            "model": type(self.model).__name__
        }
        
        # Cache result
        self.prediction_cache[cache_key] = {
            'timestamp': time.time(),
            'prediction': prediction
        }
        
        return prediction
    
    def _analyze_time_slot(self) -> str:
        """Analyze current time slot for trading quality."""
        current_hour = datetime.now().hour
        current_minute = datetime.now().minute
        
        # Market hours analysis (IST)
        if 9 <= current_hour < 9 and current_minute < 30:
            return "OPENING_VOLATILITY"
        elif 9 <= current_hour < 10:
            return "HIGH_VOLATILITY"
        elif 10 <= current_hour < 11:
            return "TRAP_ZONE_DANGER"
        elif 11 <= current_hour < 13:
            return "STABLE_RANGE"
        elif 13 <= current_hour < 14:
            return "LUNCH_LULL"
        elif 14 <= current_hour < 15:
            return "TREND_REVERSAL_GOLD"
        elif current_hour >= 15 and current_minute >= 15:
            return "CLOSING_DANGER"
        else:
            return "NEUTRAL"
    
    def _default_prediction(self, reason: str) -> dict:
        """Return default prediction when not enough data."""
        return {
            "strategy": "UNKNOWN",
            "symbol": "UNKNOWN",
            "win_rate": "N/A",
            "win_probability": 0.5,
            "time_slot_analysis": self._analyze_time_slot(),
            "confidence": "LOW",
            "recommendation": "WAIT",
            "reason": reason,
            "model": "N/A"
        }
    
    def get_market_insight(self, symbol: str) -> dict:
        """Get comprehensive market insight for dashboard."""
        candles = self.recent_candles.get(symbol, [])
        prices = self.recent_prices.get(symbol, [])
        
        if not prices:
            return {"status": "NO_DATA"}
        
        features = extract_features(
            candles=candles,
            prices=prices,
            current_volume=candles[-1].get('volume', 0) if candles else 0,
            timestamp=time.time()
        )
        
        return {
            "rsi": features.get('rsi_14', 50),
            "trend": "UP" if features.get('trend_up', 0) else ("DOWN" if features.get('trend_down', 0) else "NEUTRAL"),
            "trend_strength": features.get('trend_strength', 0),
            "volatility": features.get('atr_percent', 0),
            "volume_ratio": features.get('volume_ratio', 1),
            "is_trending": features.get('is_trending', 0) > 0,
            "regime": features.get('adx', 20),
            "time_slot": self._analyze_time_slot()
        }
