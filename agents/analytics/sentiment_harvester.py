
import logging
import random
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType

logger = logging.getLogger("SentimentAgent")

class SentimentAgent(BaseAgent):
    """
    ENGINE 21: THE SENTIMENT HARVESTER (News/Social)
    Monitors global sentiment to prevent 'Trading against Panic'.
    """
    def __init__(self):
        super().__init__("SentimentAgent")
        self.sentiment_score = 0.0 # -1.0 (Panic) to 1.0 (Euphoria)
        self.panic_keywords = ["WAR", "CRASH", "INFLATION", "SPIKE", "LOCKDOWN", "FAILURE"]
        self.current_headline = "Market stable as buyers hold ground."
        self.vix = 14.2 # Default India VIX

    async def on_start(self):
        logger.info("📰 Sentiment Harvester (News/Social) Active")

    async def on_stop(self):
        pass

    def scan_sentiment(self):
        """Simulates news scanning logic."""
        # In prod: use News API or Scraper
        # Simulated logic
        score = random.uniform(-0.5, 0.5)
        
        # Artificial panic trigger for testing
        if random.random() < 0.05:
            score = -0.9
            self.current_headline = "GLOBAL MARKETS PLUMMET ON RISING GEOPOLITICAL TENSIONS"
        else:
             self.current_headline = "Retail investors optimistic about quarterly results."
             
        self.sentiment_score = score
        return self.sentiment_score

    def check_veto(self):
        """Returns True if sentiment is too dangerous for buying."""
        self.scan_sentiment()
        if self.sentiment_score < -0.8:
            return True, f"Sentiment PANIC ({self.sentiment_score:.2f}): {self.current_headline}"
        return False, "Sentiment OK"
