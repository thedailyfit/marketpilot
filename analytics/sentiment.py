
import asyncio
import logging
import random
from datetime import datetime
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

class SentimentAgent(BaseAgent):
    """
    Analyzes Market Sentiment using VIX, News (Simulated), and Price Action.
    Produces a 'Sentiment Score' (-1.0 to +1.0).
    """
    
    def __init__(self):
        super().__init__("SentimentAgent")
        self.market_sentiment = 0.0  # Neutral
        self.fear_greed_index = 50.0 # Neutral (0-100)
        self.news_sentiment = 0.0    # Neutral
        self.vix = 14.0              # Default India VIX
        
    async def on_start(self):
        bus.subscribe(EventType.TICK, self.on_tick)
        self.logger.info("Sentiment Engine Started. Monitoring VIX & News...")
        
        # Start periodic news simulation
        asyncio.create_task(self._simulate_news_stream())

    async def on_stop(self):
        pass

    async def on_tick(self, tick):
        # In a real scenario, we'd subscribe to INDIA VIX tick
        if tick.get('symbol') == 'INDIA_VIX':
            self.vix = tick.get('ltp', 14.0)
            self._update_sentiment()
            
    def _update_sentiment(self):
        # High VIX = Fear (Bearish/Volatile), Low VIX = Complacency (Bullish/Stable)
        # Normal VIX range 12-20
        
        # Fear Greed Calculation
        if self.vix > 20: 
            fear_component = -0.6 # High fear
        elif self.vix < 12:
            fear_component = 0.4 # Greed
        else:
            fear_component = 0.0
            
        # Combine with news
        total_score = (fear_component * 0.7) + (self.news_sentiment * 0.3)
        self.market_sentiment = max(-1.0, min(1.0, total_score))
        
        # Convert to Index 0-100
        self.fear_greed_index = 50 + (self.market_sentiment * 50)
        
        # Publish if significant change
        # bus.publish(EventType.SENTIMENT_UPDATE, {"score": self.market_sentiment, "index": self.fear_greed_index})

    async def _simulate_news_stream(self):
        """Simulates incoming financial news headlines."""
        headlines = [
            ("RBI maintains status quo on repo rate", 0.2),
            ("Global markets tumble on recession fears", -0.8),
            ("FIIs net sellers for 5th consecutive day", -0.5),
            ("Tech sector shows strong earnings growth", 0.6),
            ("Oil prices surge due to geopolitical tension", -0.3),
            ("Sensex hits fresh all-time high", 0.9),
            ("Rupee weakens against Dollar", -0.2),
            ("GST collections rise by 12% YoY", 0.4)
        ]
        
        while True:
            await asyncio.sleep(random.uniform(30, 60)) # Every 30-60 secs
            news, impact = random.choice(headlines)
            
            # Decay old news sentiment
            self.news_sentiment = self.news_sentiment * 0.8
            
            # Add new impact
            self.news_sentiment += impact
            self.news_sentiment = max(-1.0, min(1.0, self.news_sentiment))
            
            self._update_sentiment()
            
            self.logger.info(f"NEWS FLASH: {news} | Impact: {impact} | Sentiment: {self.fear_greed_index:.1f}")
            
            await bus.publish(EventType.NEWS_ALERT, {
                "headline": news,
                "impact": "POSITIVE" if impact > 0 else "NEGATIVE",
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })

    def get_sentiment(self):
        return {
            "score": round(self.market_sentiment, 2),
            "fear_greed_index": round(self.fear_greed_index, 1),
            "vix": round(self.vix, 2),
            "sentiment_label": "EXTREME FEAR" if self.fear_greed_index < 20 else 
                               "FEAR" if self.fear_greed_index < 40 else 
                               "NEUTRAL" if self.fear_greed_index < 60 else 
                               "GREED" if self.fear_greed_index < 80 else "EXTREME GREED"
        }
