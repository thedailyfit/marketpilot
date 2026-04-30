"""
Trading Governor
Master gate that decides if trading should happen.
"""
import logging
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, date
from pathlib import Path
from .noise_detector import noise_detector, NoiseAnalysis
from .frequency_regulator import frequency_regulator, FrequencyStatus


@dataclass
class GovernorDecision:
    """Governor's decision on trading."""
    should_trade: bool
    reason: str
    
    # Details
    restrictions: List[str] = field(default_factory=list)
    confidence_modifier: float = 1.0  # Multiplier for signal confidence
    
    # Components
    noise_level: str = "UNKNOWN"
    frequency_status: str = "OK"
    confidence_level: str = "NORMAL"
    
    # Recommendations
    max_position_size_pct: float = 1.0  # 1.0 = full, 0.5 = half
    
    def to_dict(self) -> dict:
        return {
            "should_trade": self.should_trade,
            "reason": self.reason,
            "restrictions": self.restrictions,
            "confidence_modifier": self.confidence_modifier,
            "noise_level": self.noise_level,
            "frequency_status": self.frequency_status,
            "max_size_pct": self.max_position_size_pct
        }


class TradingGovernor:
    """
    Master gate that decides 'Should I trade today/now?'
    
    Checks:
    1. Market noise level
    2. Trade frequency limits
    3. Confidence decay from losses
    4. Session timing
    5. Special events
    
    Output:
    - should_trade: bool
    - restrictions: list
    - confidence_modifier: float
    
    This is the FINAL GATE before any trade execution.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("TradingGovernor")
        
        # Confidence tracking
        self.base_confidence = 1.0
        self.current_confidence = 1.0
        self.min_confidence = 0.3  # Never go below 30%
        
        # Override history
        self.overrides: List[Dict] = []
        
        # Special dates (no trading)
        self.no_trade_dates: List[str] = []
        
        # Event calendar
        self.events: Dict[str, str] = {}  # date -> event description
        
        # Persistence
        self.data_path = Path("data/governor/governor.json")
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._load()
    
    def should_trade_today(self, context: Dict) -> GovernorDecision:
        """
        Master decision: Should trading happen now?
        
        Args:
            context: Dict with regime, atr_percentile, agent_agreement, etc.
        
        Returns:
            GovernorDecision with full analysis
        """
        restrictions = []
        
        # Check 1: No-trade dates
        today = date.today().isoformat()
        if today in self.no_trade_dates:
            return GovernorDecision(
                should_trade=False,
                reason="No-trade date set",
                restrictions=["MARKET_HOLIDAY_OR_BLOCKED"],
                confidence_modifier=0.0
            )
        
        # Check 2: Market noise
        noise = noise_detector.measure(context)
        
        if noise.level == "EXTREME":
            return GovernorDecision(
                should_trade=False,
                reason=noise.recommendation,
                restrictions=noise.restrictions,
                confidence_modifier=0.0,
                noise_level=noise.level
            )
        
        if noise.level == "HIGH":
            restrictions.extend(noise.restrictions)
        
        # Check 3: Trade frequency
        freq = frequency_regulator.check()
        
        if freq.over_trading:
            return GovernorDecision(
                should_trade=False,
                reason=freq.recommendation,
                restrictions=["DAILY_LIMIT_REACHED"],
                confidence_modifier=0.0,
                frequency_status="BLOCKED",
                noise_level=noise.level
            )
        
        if freq.cooldown_active:
            return GovernorDecision(
                should_trade=False,
                reason=freq.recommendation,
                restrictions=["COOLDOWN_ACTIVE"],
                confidence_modifier=0.0,
                frequency_status="COOLDOWN",
                noise_level=noise.level
            )
        
        if freq.remaining == 1:
            restrictions.append("LAST_TRADE_TODAY")
        
        # Check 4: Confidence level
        if self.current_confidence < 0.5:
            if self.current_confidence < self.min_confidence:
                return GovernorDecision(
                    should_trade=False,
                    reason="Confidence too low after recent losses",
                    restrictions=["CONFIDENCE_DEPLETED"],
                    confidence_modifier=self.current_confidence,
                    confidence_level="CRITICAL",
                    noise_level=noise.level
                )
            restrictions.append("LOW_CONFIDENCE")
        
        # Check 5: Session timing
        session = self._check_session()
        if session["blocked"]:
            return GovernorDecision(
                should_trade=False,
                reason=session["reason"],
                restrictions=["BAD_SESSION_TIMING"],
                confidence_modifier=0.0,
                noise_level=noise.level
            )
        
        if session.get("warning"):
            restrictions.append(session["warning"])
        
        # Check 6: Special events
        event = self.events.get(today)
        if event:
            restrictions.append(f"EVENT_DAY: {event}")
        
        # Calculate position size
        size_pct = self._calculate_size_modifier(noise.level, freq.remaining, self.current_confidence)
        
        # All checks passed
        frequency_status = "WARNING" if freq.remaining <= 2 else "OK"
        confidence_level = "LOW" if self.current_confidence < 0.7 else "NORMAL"
        
        return GovernorDecision(
            should_trade=True,
            reason="All checks passed",
            restrictions=restrictions,
            confidence_modifier=self.current_confidence,
            noise_level=noise.level,
            frequency_status=frequency_status,
            confidence_level=confidence_level,
            max_position_size_pct=size_pct
        )
    
    def record_outcome(self, was_profitable: bool, pnl: float):
        """
        Record trade outcome to adjust confidence.
        
        Args:
            was_profitable: True if trade was profitable
            pnl: Profit/loss amount
        """
        if was_profitable:
            # Winning trade restores confidence
            self.current_confidence = min(1.0, self.current_confidence + 0.1)
        else:
            # Losing trade reduces confidence
            self.current_confidence = max(self.min_confidence, self.current_confidence - 0.15)
        
        self._save()
        
        self.logger.info(f"Confidence updated: {self.current_confidence*100:.0f}%")
    
    def reset_confidence(self):
        """Reset confidence to base level."""
        self.current_confidence = self.base_confidence
        self._save()
        self.logger.info("Confidence reset to 100%")
    
    def add_no_trade_date(self, date_str: str, reason: str = ""):
        """Add a no-trade date."""
        self.no_trade_dates.append(date_str)
        if reason:
            self.events[date_str] = reason
        self._save()
    
    def override(self, decision: str, reason: str):
        """
        Manual override of governor decision.
        
        Args:
            decision: TRADE or NO_TRADE
            reason: Why overriding
        """
        self.overrides.append({
            "timestamp": int(datetime.now().timestamp()),
            "decision": decision,
            "reason": reason
        })
        
        self._save()
        self.logger.warning(f"Governor override: {decision} - {reason}")
    
    def _check_session(self) -> Dict:
        """Check if current session is suitable."""
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        weekday = now.weekday()
        
        # Pre-market
        if hour < 9 or (hour == 9 and minute < 15):
            return {"blocked": True, "reason": "Pre-market hours"}
        
        # After market
        if hour >= 16:
            return {"blocked": True, "reason": "After market hours"}
        
        # First 15 minutes - volatile
        if hour == 9 and minute < 30:
            return {"blocked": False, "warning": "OPENING_VOLATILITY"}
        
        # Last 15 minutes
        if hour == 15 and minute >= 15:
            return {"blocked": False, "warning": "CLOSING_VOLATILITY"}
        
        # Friday late - weekend theta
        if weekday == 4 and hour >= 14:
            return {"blocked": False, "warning": "FRIDAY_AFTERNOON"}
        
        return {"blocked": False}
    
    def _calculate_size_modifier(
        self,
        noise_level: str,
        trades_remaining: int,
        confidence: float
    ) -> float:
        """Calculate recommended position size modifier."""
        modifier = 1.0
        
        # Noise adjustment
        if noise_level == "HIGH":
            modifier *= 0.75
        elif noise_level == "MEDIUM":
            modifier *= 0.9
        
        # Trades remaining adjustment
        if trades_remaining == 1:
            modifier *= 0.8  # Last trade, be conservative
        
        # Confidence adjustment
        modifier *= confidence
        
        return round(max(0.25, min(1.0, modifier)), 2)
    
    def get_status(self) -> Dict:
        """Get complete governor status."""
        return {
            "confidence": round(self.current_confidence * 100, 0),
            "today": date.today().isoformat(),
            "is_no_trade_day": date.today().isoformat() in self.no_trade_dates,
            "events_today": self.events.get(date.today().isoformat()),
            "frequency": frequency_regulator.check().to_dict(),
            "session": self._check_session()
        }
    
    def _save(self):
        """Save state to disk."""
        data = {
            "base_confidence": self.base_confidence,
            "current_confidence": self.current_confidence,
            "no_trade_dates": self.no_trade_dates,
            "events": self.events,
            "overrides": self.overrides[-10:]  # Keep last 10
        }
        
        with open(self.data_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load(self):
        """Load state from disk."""
        if not self.data_path.exists():
            return
        
        try:
            with open(self.data_path) as f:
                data = json.load(f)
            
            self.base_confidence = data.get("base_confidence", 1.0)
            self.current_confidence = data.get("current_confidence", 1.0)
            self.no_trade_dates = data.get("no_trade_dates", [])
            self.events = data.get("events", {})
            self.overrides = data.get("overrides", [])
            
        except Exception as e:
            self.logger.warning(f"Failed to load governor data: {e}")


# Singleton
trading_governor = TradingGovernor()
