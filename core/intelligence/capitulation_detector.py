"""
Capitulation Detector
Identifies potential market bottoms ("V" shape recovery).
"""
import logging
from dataclasses import dataclass

@dataclass
class BottomSignal:
    is_bottom: bool
    confidence: float
    reason: str

class CapitulationDetector:
    """
    Detects capitulation bottoms.
    
    Signals:
    1. VIX Climax: VIX spikes > 30 then drops fast.
    2. Range Exhaustion: Huge daily range followed by pinbar/reversal (simulated).
    """
    
    def __init__(self):
        self.logger = logging.getLogger("CapitulationDetector")
        self.vix_peak = 0.0
        
    def check(self, vix: float, daily_range_pct: float) -> BottomSignal:
        """
        Check for bottom signals.
        """
        is_bottom = False
        confidence = 0.0
        reason = ""
        
        # Track VIX Peak
        if vix > self.vix_peak:
            self.vix_peak = vix
            
        # VIX Reversal signal
        if self.vix_peak > 25.0:
            if vix < (self.vix_peak * 0.85): # Top dropped 15%
                is_bottom = True
                confidence = 0.7
                reason = "VIX Crush Strategy (Fear receding)"
        
        # Range Climax signal (simulated)
        if daily_range_pct > 3.0: # Huge moves usually mark ends
            if is_bottom:
                confidence = 0.9 # Confluence
                reason += " + Range Climax"
            else:
                # Weak signal on its own
                pass
                
        if is_bottom:
            self.logger.info(f"🌱 CAPITULATION SIGNAL: {reason} ({confidence*100}%)")
            
        return BottomSignal(is_bottom, confidence, reason)

# Singleton
capitulation_detector = CapitulationDetector()
