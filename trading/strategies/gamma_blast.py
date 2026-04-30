from agents.trading.strategies.base_strategy import BaseStrategy
from core.indicators import rsi, adx
from datetime import datetime

class GammaBlastStrategy(BaseStrategy):
    """
    User-Requested 'Gamma Blast Hunter' (0DTE Special).
    Logic:
    1. Active only after 1:30 PM (Gamma Risk Zone).
    2. High Momentum (RSI > 60).
    3. Explosive Volatility Expectation.
    """
    def __init__(self):
        super().__init__("GammaBlast")
        self.rsi_period = 9  # Faster RSI for scalping gamma
        self.adx_threshold = 25 # Strong Trend Required
        self.time_window_start = 1330 # 1:30 PM
        self.time_window_end = 1515 # 3:15 PM

    def on_tick(self, tick):
        self.price_history.append(tick['close'])
        if len(self.price_history) > self.history_limit:
            self.price_history.pop(0)

        self.candle_history = self._update_candles(tick)
        
        # Calculate Signals
        signal = self.calculate_signal()
        if signal:
            return signal
        return None

    def calculate_signal(self):
        if len(self.price_history) < 50:
            return None

        # 1. TIME FILTER (Gamma Zone)
        now = datetime.now()
        current_time = now.hour * 100 + now.minute
        
        # Enable on Thursday (4) or if User forces it (for testing, we assume Thursday today)
        # For MVP, we just check Time window.
        if not (self.time_window_start <= current_time <= self.time_window_end):
            return None 

        # 2. INDICATORS
        rsi_val = rsi(self.price_history, self.rsi_period)
        adx_val = adx(self.candle_history) if self.candle_history else 0
        
        # 3. LOGIC: GAMMA BURST
        # We want Explosive Moves.
        
        # BUY (Hero Zero Up)
        if rsi_val > 65 and adx_val > self.adx_threshold:
             # Additional Check: Recent large violent candle?
             return {
                "action": "BUY",
                "quantity": self.quantity,
                "strategy": "GammaBlast",
                "reason": f"GAMMA BLAST! RSI:{rsi_val:.1f} ADX:{adx_val:.1f} (HERO/ZERO)",
                "confidence": 0.9,
                "risk_type": "HIGH_RISK_HERO_ZERO"
             }

        # SELL (Hero Zero Down)
        if rsi_val < 35 and adx_val > self.adx_threshold:
             return {
                "action": "SELL",
                "quantity": self.quantity,
                "strategy": "GammaBlast",
                "reason": f"GAMMA CRASH! RSI:{rsi_val:.1f} ADX:{adx_val:.1f} (HERO/ZERO)",
                "confidence": 0.9,
                "risk_type": "HIGH_RISK_HERO_ZERO"
             }
             
        return None

    def get_state(self):
        return {
             "rsi": round(rsi(self.price_history, self.rsi_period), 2) if len(self.price_history) > 20 else 0,
             "status": "Scanning for Gamma Burst (1:30PM - 3:15PM)"
        }

    def on_candle(self, candle):
        pass

    def on_features(self, features):
        pass
