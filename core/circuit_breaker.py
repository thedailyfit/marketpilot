"""
Circuit Breaker Awareness
Handles NSE circuit breaker limits to prevent trading during halts.
"""
from datetime import datetime
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
import logging


logger = logging.getLogger(__name__)


@dataclass
class CircuitStatus:
    """Circuit breaker status."""
    symbol: str
    level_hit: int  # 0, 1, 2, or 3
    percentage: float
    direction: str  # "UP" or "DOWN"
    is_halted: bool
    resume_time: Optional[datetime]
    message: str


class CircuitBreakerMonitor:
    """
    Monitors and responds to NSE circuit breaker limits.
    
    NSE Market-Wide Circuit Breakers (MWCB) for NIFTY 50:
    - Level 1: 10% movement - 45 min halt (if before 1 PM), 15 min (1-2:30 PM), no halt after
    - Level 2: 15% movement - 1h45m halt (if before 1 PM), 45 min (1-2 PM), no halt after
    - Level 3: 20% movement - Trading halted for the day
    
    Individual Stock Circuit Limits:
    - Upper/Lower circuit: 2%, 5%, 10%, or 20% depending on category
    """
    
    # MWCB levels for Nifty
    MWCB_LEVELS = {
        1: 10.0,
        2: 15.0,
        3: 20.0
    }
    
    # Individual stock circuit limits
    STOCK_CIRCUITS = {
        "DEFAULT": 10.0,
        "VOLATILE": 5.0,
        "RESTRICTED": 2.0
    }
    
    def __init__(self):
        self.reference_prices: Dict[str, float] = {}
        self.current_status: Dict[str, CircuitStatus] = {}
        self.halted_symbols: set = set()
        
        # Index reference prices (updated daily at market open)
        self.index_references = {
            "NIFTY": 23500.0,
            "BANKNIFTY": 49000.0,
            "FINNIFTY": 24000.0
        }
    
    def set_reference_price(self, symbol: str, price: float):
        """Set daily reference price for circuit calculation."""
        self.reference_prices[symbol] = price
        logger.info(f"Circuit reference set: {symbol} = {price}")
    
    def calculate_circuit_limits(self, symbol: str) -> Tuple[float, float]:
        """Calculate upper and lower circuit limits for a symbol."""
        ref_price = self.reference_prices.get(symbol, 0)
        
        if ref_price == 0:
            return 0, float('inf')
        
        # Get circuit percentage
        if symbol.upper() in ["NIFTY", "BANKNIFTY", "FINNIFTY"]:
            # Index - use market-wide limits
            circuit_pct = 10.0  # Level 1
        else:
            # Individual stock
            circuit_pct = self.STOCK_CIRCUITS.get("DEFAULT", 10.0)
        
        upper = ref_price * (1 + circuit_pct / 100)
        lower = ref_price * (1 - circuit_pct / 100)
        
        return lower, upper
    
    def check_circuit_risk(self, symbol: str, current_price: float) -> CircuitStatus:
        """
        Check if price is approaching or has hit circuit limits.
        """
        ref_price = self.reference_prices.get(symbol)
        
        if ref_price is None or ref_price == 0:
            # No reference, assume no circuit
            return CircuitStatus(
                symbol=symbol,
                level_hit=0,
                percentage=0,
                direction="NEUTRAL",
                is_halted=False,
                resume_time=None,
                message="No circuit risk - reference not set"
            )
        
        # Calculate current movement
        movement_pct = ((current_price - ref_price) / ref_price) * 100
        direction = "UP" if movement_pct > 0 else "DOWN"
        abs_movement = abs(movement_pct)
        
        # Determine circuit level
        level_hit = 0
        is_halted = False
        message = "Normal trading"
        
        if abs_movement >= 20:
            level_hit = 3
            is_halted = True
            message = "Level 3 Circuit! Trading halted for day."
        elif abs_movement >= 15:
            level_hit = 2
            is_halted = self._is_within_halt_hours(2)
            message = "Level 2 Circuit! Possible trading halt."
        elif abs_movement >= 10:
            level_hit = 1
            is_halted = self._is_within_halt_hours(1)
            message = "Level 1 Circuit! Possible 45-min halt."
        elif abs_movement >= 8:
            message = f"Warning: {abs_movement:.1f}% move - approaching Level 1 circuit"
        elif abs_movement >= 5:
            message = f"Elevated movement: {abs_movement:.1f}%"
        
        status = CircuitStatus(
            symbol=symbol,
            level_hit=level_hit,
            percentage=round(movement_pct, 2),
            direction=direction,
            is_halted=is_halted,
            resume_time=self._calculate_resume_time(level_hit) if is_halted else None,
            message=message
        )
        
        self.current_status[symbol] = status
        
        if is_halted:
            self.halted_symbols.add(symbol)
        elif symbol in self.halted_symbols:
            self.halted_symbols.remove(symbol)
        
        return status
    
    def _is_within_halt_hours(self, level: int) -> bool:
        """Check if current time qualifies for trading halt."""
        now = datetime.now()
        hour = now.hour
        
        if level == 1:
            # Level 1: Halt before 2:30 PM
            return hour < 14 or (hour == 14 and now.minute < 30)
        elif level == 2:
            # Level 2: Halt before 2 PM
            return hour < 14
        else:
            return True  # Level 3 always halts
    
    def _calculate_resume_time(self, level: int) -> datetime:
        """Calculate when trading resumes after circuit."""
        now = datetime.now()
        
        if level == 3:
            # No resume today
            return now.replace(hour=23, minute=59)
        
        halt_durations = {
            1: 45,   # 45 minutes
            2: 105   # 1 hour 45 minutes
        }
        
        from datetime import timedelta
        return now + timedelta(minutes=halt_durations.get(level, 45))
    
    def should_trade(self, symbol: str, current_price: float) -> Tuple[bool, str]:
        """
        Determine if trading is safe based on circuit status.
        
        Returns:
            (can_trade, reason)
        """
        status = self.check_circuit_risk(symbol, current_price)
        
        if status.is_halted:
            return False, f"Trading halted: {status.message}"
        
        if status.level_hit >= 2:
            return False, f"Level {status.level_hit} Circuit - Risk too high"
        
        if status.level_hit == 1:
            # Level 1 - can trade but with caution
            return True, "Level 1 Circuit - Trade with tight SL"
        
        # Check if approaching circuit
        abs_pct = abs(status.percentage)
        if abs_pct >= 8:
            return True, f"Warning: {abs_pct:.1f}% move - approaching circuit"
        
        return True, "Normal trading conditions"
    
    def is_symbol_halted(self, symbol: str) -> bool:
        """Quick check if symbol is currently halted."""
        return symbol in self.halted_symbols
    
    def get_all_halted(self) -> set:
        """Get all currently halted symbols."""
        return self.halted_symbols.copy()
    
    def get_risk_adjustment(self, symbol: str, current_price: float) -> Dict:
        """
        Get risk parameter adjustments based on circuit proximity.
        """
        status = self.check_circuit_risk(symbol, current_price)
        abs_pct = abs(status.percentage)
        
        # Default adjustments
        adjustments = {
            "position_size_multiplier": 1.0,
            "sl_multiplier": 1.0,
            "max_positions": 3,
            "take_new_trades": True
        }
        
        if abs_pct >= 8:
            # Approaching circuit - reduce risk
            adjustments["position_size_multiplier"] = 0.5
            adjustments["sl_multiplier"] = 1.5
            adjustments["max_positions"] = 1
        
        if abs_pct >= 10:
            # At circuit - minimal new trades
            adjustments["position_size_multiplier"] = 0.25
            adjustments["max_positions"] = 1
            adjustments["take_new_trades"] = False
        
        if status.is_halted:
            adjustments["take_new_trades"] = False
            adjustments["max_positions"] = 0
        
        return adjustments


# Global instance
circuit_monitor = CircuitBreakerMonitor()
