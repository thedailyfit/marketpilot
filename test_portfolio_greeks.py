"""
Portfolio Greeks & Risk Verification
Tests GreeksPortfolioTracker, ThetaBudgetManager, and VegaExposureLimit.
"""
import logging
from core.risk.greeks_portfolio import GreeksPortfolioTracker, Position
from core.risk.theta_budget import theta_budget_manager
from core.risk.vega_limit import vega_exposure_limit

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

def test_portfolio_risk():
    print("="*60)
    print("PORTFOLIO GREEKS & RISK VERIFICATION (Level-09)")
    print("="*60)
    
    # 1. Initialize Tracker
    tracker = GreeksPortfolioTracker(capital=500000)
    
    # Reset budgets for test
    theta_budget_manager.set_budget(500.0)
    vega_exposure_limit.update_capital(500000)
    vega_exposure_limit.max_vega_pct = 0.02
    
    print("\n[1] Adding Positions...")
    
    # Add a Naked Long Call (High Theta Burn, High Vega)
    # 1 lot (50 qty) of NIFTY CE
    long_call = Position(
        symbol="NIFTY", strike=22000, expiry="2024-03-28", option_type="CE",
        quantity=50, entry_price=100.0, current_price=100.0,
        delta=0.5, gamma=0.01, theta=-10.0, vega=5.0
    )
    tracker.add_position("POS_1", long_call)
    
    # Add a Credit Spread (Positive Theta, Negative Vega)
    # Short Call 22200 (Qty -50), Long Call 22400 (Qty 50)
    short_leg = Position(
        symbol="NIFTY", strike=22200, expiry="2024-03-28", option_type="CE",
        quantity=-50, entry_price=50.0, current_price=50.0,
        delta=0.3, gamma=0.005, theta=-5.0, vega=3.0
    )
    long_leg = Position(
        symbol="NIFTY", strike=22400, expiry="2024-03-28", option_type="CE",
        quantity=50, entry_price=20.0, current_price=20.0,
        delta=0.1, gamma=0.002, theta=-2.0, vega=1.0
    )
    tracker.add_position("POS_2", short_leg)
    tracker.add_position("POS_3", long_leg)
    
    # 2. Check Portfolio Greeks
    print("\n[2] Checking Portfolio Greeks...")
    greeks = tracker.get_greeks()
    print(f"Total Delta: {greeks.total_delta}")
    print(f"Total Theta (Daily Burn): {greeks.total_theta}")
    print(f"Total Vega: {greeks.total_vega}")
    
    # 3. Feed to Risk Managers
    print("\n[3] Validating Risk Limits...")
    theta_budget_manager.update_current_theta(greeks.total_theta)
    vega_exposure_limit.update_current_vega(greeks.total_vega)
    
    theta_status = theta_budget_manager.get_status()
    print(f"Theta Budget Utilization: {theta_status.utilization_pct:.1f}% (₹{theta_status.current_theta}/₹{theta_status.daily_budget})")
    
    vega_status = vega_exposure_limit.get_status()
    print(f"Vega Limit Utilization: {vega_status.utilization_pct:.1f}% (Vega: {vega_status.current_vega}/Max: {vega_status.max_vega})")
    print(f"10% IV Crush Impact: ₹{vega_status.iv_crush_10_impact}")
    
    # 4. Attempt to add another high risk position
    print("\n[4] Simulating Risk Gate...")
    new_position_theta = 20.0 * 50  # 1000 daily burn
    new_position_vega = 10.0 * 50   # 500 vega
    
    theta_check = theta_budget_manager.can_add_position(new_position_theta)
    print(f"Adding high-theta position allowed? {theta_check['allowed']}")
    if not theta_check['allowed']:
        print(f"Reason: {theta_check['reason']}")
        
    vega_check = vega_exposure_limit.check(new_position_vega)
    print(f"Adding high-vega position allowed? {vega_check['allowed']}")
    
    print("\n✅ Level-09 Risk Validation Complete.")

if __name__ == "__main__":
    test_portfolio_risk()
