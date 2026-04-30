"""
Options Idea Generator
Converts Galaxy consensus signals into complete trade ideas.
"""
import logging
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date
from core.options.chain_snapshot import OptionSnapshot
from core.options.strike_optimizer import strike_optimizer, StrikeScore
from core.options.expiry_evaluator import expiry_evaluator
from core.options.iv_surface import IVSurface
from core.options.payoff import payoff_simulator
from core.intelligence.confluence_engine import confluence_engine
from core.intelligence.gamma_engine import gamma_engine
from core.volume.zone_engine import zone_engine


@dataclass
class TradeIdea:
    """
    Complete trade idea with structure, risk, and invalidation.
    
    This is NOT just a signal — it's a fully formed trade plan.
    """
    id: str
    timestamp: int
    signal: str             # BULLISH, BEARISH
    confidence: float       # 0-1
    status: str = "GENERATED"  # GENERATED, APPROVED, REJECTED, EXECUTED, CLOSED
    
    # Signal origin
    source_agents: List[str] = field(default_factory=list)
    regime: str = "UNKNOWN"
    
    # Option structure
    symbol: str = ""
    underlying_price: float = 0.0
    strike: float = 0.0
    expiry: str = ""
    option_type: str = ""   # CE, PE
    premium: float = 0.0
    
    # Sizing
    quantity: int = 0
    lot_size: int = 50      # NIFTY default
    total_premium: float = 0.0
    
    # Risk parameters
    stop_loss_price: float = 0.0
    stop_loss_pct: float = 0.0
    target_1_price: float = 0.0
    target_1_pct: float = 0.0
    target_2_price: float = 0.0
    target_2_pct: float = 0.0
    max_loss: float = 0.0
    risk_reward: float = 0.0
    
    # Invalidation
    invalidation_spot: float = 0.0
    invalidation_reason: str = ""
    
    # Greeks
    delta: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    
    # Stress test results
    iv_crush_10_impact: float = 0.0
    theta_1day_impact: float = 0.0
    
    # Reasoning
    why_this_trade: str = ""
    how_it_fails: str = ""
    
    # Scores
    idea_score: float = 0.0
    liquidity_score: float = 0.0
    timing_score: float = 0.0
    confluence_score: float = 0.0
    
    # Rejection info
    rejection_reason: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def is_viable(self) -> bool:
        return self.status == "GENERATED" and self.rejection_reason is None


class OptionsIdeaGenerator:
    """
    Converts signals into complete trade ideas.
    
    Process:
    1. Receive signal (direction, confidence, agents)
    2. Evaluate IV regime
    3. Select optimal expiry
    4. Rank and select strike
    5. Calculate risk levels
    6. Stress test
    7. Generate reasoning
    8. Check rejection criteria
    
    Output: Complete TradeIdea or rejected idea with reason
    """
    
    def __init__(self):
        self.logger = logging.getLogger("OptionsIdeaGenerator")
        
        # Risk parameters
        self.default_stop_loss_pct = 0.50   # 50% of premium
        self.default_target_1_pct = 0.50    # 50% gain
        self.default_target_2_pct = 1.00    # 100% gain
        self.max_premium_pct = 0.02         # Max 2% of capital per trade
        
        # Rejection thresholds
        self.min_liquidity_score = 40
        self.max_iv_percentile = 80         # Avoid buying at high IV
        self.max_theta_daily_pct = 15       # Max 15% theta per day
        self.min_days_to_expiry = 2
    
    def generate(
        self,
        signal: Dict,
        chain: List[OptionSnapshot],
        spot: float,
        capital: float,
        iv_surface: Optional[IVSurface] = None,
        symbol: str = "NIFTY"
    ) -> TradeIdea:
        """
        Generate trade idea from signal.
        
        Args:
            signal: Dict with direction, confidence, agents, regime
            chain: Option chain snapshot
            spot: Current spot price
            capital: Trading capital
            iv_surface: Optional IV surface
            symbol: Underlying symbol
        
        Returns:
            TradeIdea (may be rejected)
        """
        idea_id = str(uuid.uuid4())[:8]
        timestamp = int(datetime.now().timestamp())
        
        direction = signal.get("direction", "BULLISH")
        confidence = signal.get("confidence", 0.5)
        agents = signal.get("agents", [])
        regime = signal.get("regime", "UNKNOWN")
        horizon = signal.get("horizon", "INTRADAY")
        
        # Create base idea
        idea = TradeIdea(
            id=idea_id,
            timestamp=timestamp,
            signal=direction,
            confidence=confidence,
            source_agents=agents[:5],
            regime=regime,
            symbol=symbol,
            underlying_price=spot
        )
        
        # Step 1: Check IV regime
        rejection = self._check_iv_regime(iv_surface)
        if rejection:
            idea.status = "REJECTED"
            idea.rejection_reason = rejection
            return idea
        
        # Step 2: Get optimal expiry
        expiry_rec = expiry_evaluator.evaluate(horizon, iv_surface=iv_surface)
        
        # Step 3: Rank strikes
        filtered_chain = [o for o in chain if o.expiry == expiry_rec.recommended_expiry]
        if not filtered_chain:
            filtered_chain = chain  # Fallback to full chain
        
        strikes = strike_optimizer.rank_strikes(
            direction, spot, filtered_chain, capital, iv_surface=iv_surface
        )
        
        if not strikes:
            idea.status = "REJECTED"
            idea.rejection_reason = "No viable strikes found"
            return idea
        
        # Step 4: Select best strike
        best = strikes[0]
        option = self._find_option(chain, best.strike, best.expiry, best.option_type)
        
        if not option:
            idea.status = "REJECTED"
            idea.rejection_reason = "Could not find option in chain"
            return idea
        
        # Step 5: Check rejections
        rejection = self._check_rejections(option, iv_surface, best)
        if rejection:
            idea.status = "REJECTED"
            idea.rejection_reason = rejection
            return idea
        
        # Step 6: Calculate sizing
        max_premium = capital * self.max_premium_pct
        lot_size = 50 if symbol == "NIFTY" else 25  # BANKNIFTY = 25
        premium_per_lot = option.ltp * lot_size
        
        quantity = min(
            int(max_premium / premium_per_lot),
            5  # Max 5 lots per idea
        )
        
        if quantity < 1:
            idea.status = "REJECTED"
            idea.rejection_reason = f"Premium too high: ₹{premium_per_lot:.0f}/lot > budget"
            return idea
        
        # Step 7: Calculate risk levels
        entry = option.ltp
        stop_loss = entry * (1 - self.default_stop_loss_pct)
        target_1 = entry * (1 + self.default_target_1_pct)
        target_2 = entry * (1 + self.default_target_2_pct)
        max_loss = entry * quantity * lot_size
        
        risk_reward = self.default_target_1_pct / self.default_stop_loss_pct
        
        # Step 8: Stress test
        stress = payoff_simulator.stress_test(option, spot)
        
        # Step 9: Calculate invalidation
        invalid_spot, invalid_reason = self._calculate_invalidation(
            direction, spot, option.strike, signal
        )
        
        # Step 10: Confluence Score
        active_zones = zone_engine.get_active_zones()
        gamma_obj = gamma_engine.current_state  # Direct attribute access (no get_state method)
        
        confluence_report = confluence_engine.evaluate(
            spot_price=spot,
            direction=direction,
            active_zones=active_zones,
            gamma_state=gamma_obj
        )
        
        # Step 11: Generate reasoning
        why = self._generate_why(signal, option, iv_surface, best)
        
        # Add confluence reasons to why
        if confluence_report.reasons:
            why += "\n\nCONFLUENCE:\n" + "\n".join([f"- {r}" for r in confluence_report.reasons])
            
        how_fails = self._generate_how_fails(option, spot, iv_surface)
        
        # Populate idea
        idea.strike = best.strike
        idea.expiry = best.expiry
        idea.option_type = best.option_type
        idea.premium = entry
        idea.quantity = quantity
        idea.lot_size = lot_size
        idea.total_premium = entry * quantity * lot_size
        
        idea.stop_loss_price = stop_loss
        idea.stop_loss_pct = self.default_stop_loss_pct * 100
        idea.target_1_price = target_1
        idea.target_1_pct = self.default_target_1_pct * 100
        idea.target_2_price = target_2
        idea.target_2_pct = self.default_target_2_pct * 100
        idea.max_loss = max_loss
        idea.risk_reward = risk_reward
        
        idea.invalidation_spot = invalid_spot
        idea.invalidation_reason = invalid_reason
        
        idea.delta = option.delta
        idea.theta = option.theta
        idea.vega = option.vega
        
        idea.iv_crush_10_impact = stress.iv_crush_10
        idea.theta_1day_impact = stress.theta_1day
        
        idea.why_this_trade = why
        idea.how_it_fails = how_fails
        
        idea.idea_score = best.total_score
        idea.liquidity_score = best.liquidity_score
        idea.timing_score = self._calculate_timing_score()
        idea.confluence_score = confluence_report.score
        
        idea.status = "GENERATED"
        
        self.logger.info(
            f"💡 Idea Generated: {symbol} {best.strike} {best.option_type} "
            f"@ ₹{entry:.2f} | Score: {best.total_score:.0f}"
        )
        
        return idea
    
    def _find_option(
        self,
        chain: List[OptionSnapshot],
        strike: float,
        expiry: str,
        option_type: str
    ) -> Optional[OptionSnapshot]:
        """Find specific option in chain."""
        for opt in chain:
            if (opt.strike == strike and 
                opt.expiry == expiry and 
                opt.option_type == option_type):
                return opt
        return None
    
    def _check_iv_regime(self, iv_surface: Optional[IVSurface]) -> Optional[str]:
        """Check if IV regime is suitable for buying."""
        if not iv_surface:
            return None
        
        if iv_surface.regime == "CRUSH_RISK":
            return f"IV crush risk detected - percentile at {iv_surface.iv_percentile:.0f}%"
        
        if iv_surface.iv_percentile > self.max_iv_percentile:
            return f"IV too high ({iv_surface.iv_percentile:.0f}%) - expensive premiums"
        
        return None
    
    def _check_rejections(
        self,
        option: OptionSnapshot,
        iv_surface: Optional[IVSurface],
        score: StrikeScore
    ) -> Optional[str]:
        """Check various rejection criteria."""
        
        # Liquidity check
        if score.liquidity_score < self.min_liquidity_score:
            return f"Insufficient liquidity (score: {score.liquidity_score:.0f})"
        
        # Theta check
        if option.ltp > 0:
            theta_pct = abs(option.theta) / option.ltp * 100
            if theta_pct > self.max_theta_daily_pct:
                return f"Theta too aggressive: {theta_pct:.1f}% daily decay"
        
        # Days to expiry check
        try:
            expiry_date = datetime.strptime(option.expiry, '%Y-%m-%d').date()
            days_left = (expiry_date - date.today()).days
            if days_left < self.min_days_to_expiry:
                return f"Expiry too close: only {days_left} days"
        except:
            pass
        
        # Volume check
        if option.volume < 500:
            return f"Insufficient volume: {option.volume}"
        
        return None
    
    def _calculate_invalidation(
        self,
        direction: str,
        spot: float,
        strike: float,
        signal: Dict
    ) -> Tuple[float, str]:
        """Calculate trade invalidation level."""
        
        # Use signal's invalidation if provided
        if "invalidation_level" in signal:
            return signal["invalidation_level"], "Signal invalidation level breached"
        
        # Default: 2% opposite move
        if direction == "BULLISH":
            invalid_spot = spot * 0.98  # 2% below current
            reason = "Spot breaks below 2% from entry"
        else:
            invalid_spot = spot * 1.02  # 2% above current
            reason = "Spot breaks above 2% from entry"
        
        return round(invalid_spot, 2), reason
    
    def _generate_why(
        self,
        signal: Dict,
        option: OptionSnapshot,
        iv_surface: Optional[IVSurface],
        score: StrikeScore
    ) -> str:
        """Generate 'Why this trade' reasoning."""
        parts = []
        
        # Direction
        parts.append(f"DIRECTION: {signal.get('direction')} with {signal.get('confidence', 0)*100:.0f}% confidence")
        
        # Regime
        regime = signal.get('regime', 'UNKNOWN')
        if regime in ["TREND_UP", "TREND_DOWN"]:
            parts.append(f"REGIME: {regime} — favorable for directional plays")
        elif regime == "CHOP":
            parts.append(f"REGIME: {regime} — high conviction required")
        
        # Agents
        agents = signal.get('agents', [])[:3]
        if agents:
            parts.append(f"AGENTS: {', '.join(agents)} aligned")
        
        # IV
        if iv_surface:
            if iv_surface.iv_percentile < 30:
                parts.append(f"IV: {iv_surface.iv_percentile:.0f}th percentile — cheap premiums")
            else:
                parts.append(f"IV: {iv_surface.iv_percentile:.0f}th percentile")
        
        # Strike selection
        parts.append(f"STRIKE: {score.strike} selected (score: {score.total_score:.0f})")
        parts.extend(score.reasons[:2])
        
        return "\n".join(parts)
    
    def _generate_how_fails(
        self,
        option: OptionSnapshot,
        spot: float,
        iv_surface: Optional[IVSurface]
    ) -> str:
        """Generate 'How it fails' reasoning."""
        parts = []
        
        # Directional failure
        parts.append(f"1. Spot reverses and moves against position")
        
        # IV crush
        if iv_surface and iv_surface.iv_percentile > 50:
            crush_loss = option.vega * 10  # 10% IV crush
            parts.append(f"2. IV crushes 10% — loses ₹{crush_loss:.0f} per lot")
        else:
            parts.append(f"2. IV crushes post-event — vega exposure: {option.vega:.1f}")
        
        # Theta decay
        parts.append(f"3. Time decay: ₹{abs(option.theta):.1f}/day if spot flat")
        
        # Regime change
        parts.append(f"4. Regime shifts to CHOP — directional edge disappears")
        
        return "\n".join(parts)
    
    def _calculate_timing_score(self) -> float:
        """Calculate timing score based on market session."""
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        weekday = now.weekday()
        
        score = 50  # Base
        
        # Opening hour (9:15-10:15) - avoid
        if hour == 9 or (hour == 10 and minute < 15):
            score -= 20
        
        # Last hour (2:30-3:30) - theta accelerates
        if (hour == 14 and minute >= 30) or hour >= 15:
            score -= 10
        
        # Sweet spot (10:15-2:00)
        if 10 <= hour < 14:
            score += 20
        
        # Friday - weekend theta
        if weekday == 4:
            score -= 15
        
        # Monday morning - gap risk
        if weekday == 0 and hour < 10:
            score -= 10
        
        return max(0, min(100, score))
    
    def format_idea_card(self, idea: TradeIdea) -> str:
        """Format idea as readable card."""
        if idea.status == "REJECTED":
            return f"""
❌ IDEA REJECTED
Reason: {idea.rejection_reason}
Signal: {idea.signal} {idea.confidence*100:.0f}%
"""
        
        return f"""
💡 TRADE IDEA: {idea.symbol} {idea.strike} {idea.option_type}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 Direction: {idea.signal} | Confidence: {idea.confidence*100:.0f}%
⏱️  Expiry: {idea.expiry} | Premium: ₹{idea.premium:.2f}

📊 STRUCTURE
   Quantity: {idea.quantity} lots ({idea.lot_size}/lot)
   Total: ₹{idea.total_premium:.0f}
   
🎯 TARGETS
   Stop Loss: ₹{idea.stop_loss_price:.2f} (-{idea.stop_loss_pct:.0f}%)
   Target 1: ₹{idea.target_1_price:.2f} (+{idea.target_1_pct:.0f}%)
   Target 2: ₹{idea.target_2_price:.2f} (+{idea.target_2_pct:.0f}%)

⚠️  RISK
   Max Loss: ₹{idea.max_loss:.0f}
   Risk/Reward: {idea.risk_reward:.1f}x
   Delta: {idea.delta:.2f} | Theta: ₹{abs(idea.theta):.1f}/day

📝 WHY THIS TRADE:
{idea.why_this_trade}

❌ HOW IT FAILS:
{idea.how_it_fails}

🔒 INVALIDATION: {idea.invalidation_reason}
   Below ₹{idea.invalidation_spot:.2f}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Score: {idea.idea_score:.0f}/100 | Confluence: {idea.confluence_score:.0f}/100 | Liquidity: {idea.liquidity_score:.0f}
"""


# Singleton
options_idea_generator = OptionsIdeaGenerator()
