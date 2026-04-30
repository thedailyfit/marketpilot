"""
Multi-Leg Execution Verification
Tests the Strategy Builder and Leg Risk Simulator.
"""
import logging
import time
from core.options.chain_snapshot import OptionSnapshot
from core.options.strategy_builder import strategy_builder, SpreadStructure
from core.execution.leg_risk import leg_risk_simulator, LegRiskReport

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger("TestMultiLeg")

def create_mock_chain():
    """Create a mock option chain for NIFTY (Spot 22000)."""
    ts = int(time.time())
    chain = []
    
    # Strikes: 21800 to 22200
    for strike in range(21800, 22250, 50):
        # Calls
        chain.append(OptionSnapshot(
            symbol="NIFTY", strike=strike, expiry="2024-03-28", option_type="CE",
            ltp=max(0, 22000 - strike) + 50, # Intrinsic + Time
            bid=max(0, 22000 - strike) + 48,
            ask=max(0, 22000 - strike) + 52,
            oi=10000, volume=5000, iv=0.15, delta=0.5, gamma=0.01, theta=-10, vega=5, timestamp=ts
        ))
        # Puts
        chain.append(OptionSnapshot(
            symbol="NIFTY", strike=strike, expiry="2024-03-28", option_type="PE",
            ltp=max(0, strike - 22000) + 50,
            bid=max(0, strike - 22000) + 48,
            ask=max(0, strike - 22000) + 52,
            oi=10000, volume=5000, iv=0.15, delta=-0.5, gamma=0.01, theta=-10, vega=5, timestamp=ts
        ))
    return chain

def test_bear_put_spread():
    """
    Scenario: User wants to buy 22000 PE (ATM).
    Convert to Bear Put Spread to reduce cost.
    """
    print("\n" + "="*60)
    print("SCENARIO 1: BUILD BEAR PUT SPREAD")
    print("="*60)
    
    chain = create_mock_chain()
    
    # Base Idea: Long 22000 PE
    base_option = next(o for o in chain if o.strike == 22000 and o.option_type == "PE")
    
    print(f"Base Option: {base_option.symbol} {base_option.strike} {base_option.option_type}")
    print(f"Cost (Ask): {base_option.ask}")
    
    # Risk Budget: 40 points (we want to pay max 40 net)
    risk_budget = 40.0
    print(f"Risk Budget: {risk_budget}")
    
    spread = strategy_builder.build_vertical_spread(
        base_option=base_option,
        direction="BEARISH",
        chain=chain,
        risk_budget=risk_budget
    )
    
    if spread:
        print("\n✅ Spread Constructed:")
        print(f"Type: {spread.name}")
        print(f"Long Leg: {spread.long_leg.strike} PE (Ask: {spread.long_leg.ask})")
        print(f"Short Leg: {spread.short_leg.strike} PE (Bid: {spread.short_leg.bid})")
        print(f"Net Debit: {spread.net_debit} (Budget: {risk_budget})")
        print(f"Max Loss: {spread.max_loss}")
        print(f"Max Gain: {spread.max_gain}")
        print(f"R:R Ratio: {spread.risk_reward_ratio}")
        
        # Validation
        assert spread.net_debit <= risk_budget, "Net debit exceeded budget!"
        assert spread.short_leg.strike < spread.long_leg.strike, "Bear Put Spread structure invalid!"
        return spread
    else:
        print("❌ Failed to build spread.")
        return None

def test_legging_risk(spread: SpreadStructure):
    """
    Test leg risk simulator on the constructed spread.
    """
    print("\n" + "="*60)
    print("SCENARIO 2: ASSESS LEGGING RISK")
    print("="*60)
    
    # Scenario A: Normal liquidity
    risk_report = leg_risk_simulator.assess_legging_risk(
        long_leg=spread.long_leg,
        short_leg=spread.short_leg,
        max_risk_budget=50.0 # Slightly higher tolerance
    )
    
    print("Case A (Normal):")
    print(f"Safe: {risk_report.is_safe}")
    print(f"Est Slippage: {risk_report.estimated_slippage}")
    print(f"Worst Case Loss: {risk_report.worst_case_loss}")
    
    if risk_report.is_safe:
        print("✅ Risk Within Limits")
    else:
        print("❌ Risk Too High")
        
    # Scenario B: Low Liquidity Short Leg
    print("\nCase B (Low Liquidity Short):")
    short_leg_illiquid = spread.short_leg
    short_leg_illiquid.oi = 100 # Low OI
    
    risk_report_b = leg_risk_simulator.assess_legging_risk(
        long_leg=spread.long_leg,
        short_leg=short_leg_illiquid,
        max_risk_budget=50.0
    )
    
    print(f"Safe: {risk_report_b.is_safe}")
    print(f"Est Slippage: {risk_report_b.estimated_slippage}")
    print(f"Worst Case Loss: {risk_report_b.worst_case_loss}")
    
    if len(risk_report_b.warnings) > 0:
        print(f"✅ Correctly warned about liquidity: {risk_report_b.warnings[0]}")
    else:
        print("❌ Failed to warn about liquidity")

if __name__ == "__main__":
    spread = test_bear_put_spread()
    if spread:
        test_legging_risk(spread)
