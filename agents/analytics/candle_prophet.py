
import asyncio
import logging
from collections import defaultdict
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("CandleProphetAgent")

class CandleProphetAgent(BaseAgent):
    """
    ENGINE 7: CANDLE PROPHET (Probability Engine)
    Uses Markov Chain logic to predict the next candle based on recent history.
    """
    def __init__(self):
        super().__init__("CandleProphetAgent")
        self.history = [] # Last N candles: 'G' (Green) or 'R' (Red)
        self.transition_matrix = defaultdict(lambda: {'G': 0, 'R': 0, 'total': 0})
        self.min_data_points = 10 # Low for prototype, would be 5000+ in prod
        
        # Seed with some diverse dummy data for the prototype to work immediately
        self._seed_data()

    def _seed_data(self):
        """Seeds the matrix with common patterns for immediate utility."""
        patterns = [
            ('G', 'G', 'G', 'R'), # 3 Greens -> Red Reversal
            ('R', 'R', 'R', 'G'), # 3 Reds -> Green Reversal
            ('G', 'R', 'G', 'R'), # Chop
            ('R', 'G', 'R', 'G')  # Chop
        ]
        for p in patterns:
            for i in range(10): # Weight them
                key = "".join(p[:-1])
                outcome = p[-1]
                self.transition_matrix[key][outcome] += 1
                self.transition_matrix[key]['total'] += 1

    async def on_start(self):
        bus.subscribe(EventType.CANDLE_DATA, self.on_candle)
        logger.info("🔮 CandleProphet (Statistical Probability) Active")

    async def on_stop(self):
        pass

    async def on_candle(self, candle: dict):
        """Process new candle and update probability model."""
        direction = 'G' if candle['close'] >= candle['open'] else 'R'
        self.history.append(direction)
        
        # Keep history short for pattern matching window (e.g., lookback 3)
        if len(self.history) > 4: 
            # Learn from the JUST completed sequence
            # Pattern: History[-4], History[-3], History[-2] -> Outcome: History[-1]
            pattern_key = "".join(self.history[-4:-1])
            outcome = self.history[-1]
            
            self.transition_matrix[pattern_key][outcome] += 1
            self.transition_matrix[pattern_key]['total'] += 1
            
            # Trim buffer
            self.history.pop(0)
            
        # Predict NEXT candle
        if len(self.history) >= 3:
            current_pattern = "".join(self.history[-3:])
            prediction = self._predict(current_pattern)
            
            if prediction:
                logger.info(f"🔮 PROPHET: Pattern [{current_pattern}] -> Next: {prediction['direction']} ({prediction['prob']:.0%})")
                
                await bus.publish(EventType.ANALYSIS, {
                    "source": "CandleProphetAgent",
                    "type": "PROBABILITY_FORECAST",
                    "data": {
                        "pattern": current_pattern,
                        "prediction": prediction
                    }
                })

    def _predict(self, pattern):
        stats = self.transition_matrix.get(pattern)
        if not stats or stats['total'] < 3: return None # Not enough data
        
        prob_g = stats['G'] / stats['total']
        prob_r = stats['R'] / stats['total']
        
        if prob_g > 0.6: return {"direction": "GREEN", "prob": prob_g}
        if prob_r > 0.6: return {"direction": "RED", "prob": prob_r}
        return {"direction": "UNCERTAIN", "prob": 0.5}
