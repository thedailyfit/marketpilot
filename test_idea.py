"""
Test script for OptionsIdeaGenerator + ConfluenceEngine.
"""
import logging
from core.ideas.idea_generator import options_idea_generator
from core.options.chain_snapshot import OptionSnapshot
from core.volume.zone_engine import zone_engine, InstitutionalZone
from core.intelligence.gamma_engine import gamma_engine, GammaState

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

def test_full_idea_generation():
    print("="*60)
    print("IDEA GENERATOR + CONFLUENCE VERIFICATION")
    print("="*60)
    
    # Setup Dummies
    spot = 22000.0
    capital = 500000.0
    
    # Dummy Option Chain
    chain = [
        OptionSnapshot("NIFTY", 22000, "2026-03-25", "CE", 100.0, 99.0, 101.0, 10000, 50000, 0.15, 0.5, 0.01, -5.0, 10.0, 0),
        OptionSnapshot("NIFTY", 22100, "2026-03-25", "CE", 50.0, 49.0, 51.0, 5000, 20000, 0.15, 0.3, 0.005, -3.0, 8.0, 0),
        OptionSnapshot("NIFTY", 21900, "2026-03-25", "PE", 90.0, 89.0, 91.0, 12000, 60000, 0.16, -0.4, 0.012, -4.5, 9.5, 0)
    ]
    
    # Inject Institutional Zones
    poc_zone = InstitutionalZone(
        zone_id="Z1", poc=22000.0, upper_bound=22020.0, lower_bound=21980.0,
        strength=80.0, created_at=0, is_fresh=True
    )
    zone_engine.zones = [poc_zone]
    
    # Inject Gamma State
    gamma_engine.current_state = GammaState(
        spot=22000.0, max_pain=22500.0, gamma_flip=21800.0,
        zone="NEGATIVE", pressure="EXPANSION", net_gamma=-5000000,
        timestamp=100
    )
    
    # Create Signal
    signal = {
        "direction": "BULLISH",
        "confidence": 0.85,
        "agents": ["TrendAgent", "BreakoutAgent"],
        "regime": "TREND_UP",
        "horizon": "INTRADAY"
    }
    
    # Generate Idea
    idea = options_idea_generator.generate(
        signal=signal,
        chain=chain,
        spot=spot,
        capital=capital
    )
    
    print(options_idea_generator.format_idea_card(idea))
    
    if idea.confluence_score > 0:
        print("✅ PASS: Confluence Engine successfully integrated into TradeIdea.")
    else:
        print("❌ FAIL: Confluence score is 0.")

if __name__ == "__main__":
    test_full_idea_generation()
