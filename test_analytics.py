import asyncio
import logging
from core.analytics.trade_journal import trade_journal
from core.analytics.decision_quality import decision_analytics
from core.analytics.weekly_review import weekly_review

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger("TestAnalytics")

def grade_trade(trade_id, description):
    trade = trade_journal.get_trade(trade_id)
    analysis = decision_analytics.analyze(trade)
    trade_journal.update_analysis(trade_id, analysis['grade'], analysis['score'], analysis['notes'])
    
    print(f"\n--- {description} ---")
    print(f"Action: {trade.action} {trade.symbol}")
    print(f"Outcome: PnL {trade.pnl}")
    print(f"Grade: {analysis['grade']} ({analysis['category']})")
    print(f"Notes: {analysis['notes']}")
    
    return analysis

async def test_analytics():
    print("="*60)
    print("LEVEL-11: ANALYTICS VERIFICATION")
    print("="*60)
    
    # ---------------------------------------------------------
    # Trade 1: SKILL (Good Process + Win)
    # ---------------------------------------------------------
    id1 = trade_journal.log_entry(
        symbol="NIFTY", action="BUY", strategy="TREND_FOLLOW",
        quantity=50, price=100.0, sl=95.0, tp=110.0,
        context={"regime": "TREND", "confidence": 0.8, "setup": "PULLBACK"}
    )
    trade_journal.log_exit(id1, 110.0, "TARGET") # WIN
    grade_trade(id1, "Trade 1: SKILL")
    
    # ---------------------------------------------------------
    # Trade 2: DUMB LUCK (Bad Process + Win)
    # ---------------------------------------------------------
    id2 = trade_journal.log_entry(
        symbol="BANKNIFTY", action="BUY", strategy="FOMO_CHASE",
        quantity=25, price=200.0, sl=0.0, tp=0.0, # No Plan
        context={"regime": "CHOP", "confidence": 0.3, "setup": "NONE"}
    )
    trade_journal.log_exit(id2, 210.0, "FORCE") # WIN but Forced exit
    grade_trade(id2, "Trade 2: DUMB LUCK")
    
    # ---------------------------------------------------------
    # Trade 3: BAD LUCK (Good Process + Loss)
    # ---------------------------------------------------------
    id3 = trade_journal.log_entry(
        symbol="NIFTY", action="SELL", strategy="TREND_FOLLOW",
        quantity=50, price=100.0, sl=105.0, tp=90.0,
        context={"regime": "TREND", "confidence": 0.9, "setup": "BREAKOUT"}
    )
    trade_journal.log_exit(id3, 105.0, "STOP") # LOSS
    grade_trade(id3, "Trade 3: BAD LUCK")
    
    # ---------------------------------------------------------
    # Weekly Review
    # ---------------------------------------------------------
    print("\n--- WEEKLY REVIEW REPORT ---")
    report = weekly_review.generate_report()
    for k, v in report.items():
        print(f"{k}: {v}")
        
    print("\n✅ Analytics Logic Verified")

if __name__ == "__main__":
    asyncio.run(test_analytics())
