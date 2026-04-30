"""
Decision Quality Analytics
Judges the QUALITY of a decision independent of the OUTCOME.
"""
import logging
from .trade_journal import JournalEntry

class DecisionQuality:
    """
    Grades trades based on Process vs Outcome matrix.
    
    Matrix:
    - Good Process + Good Outcome = SKILL (Reinforce)
    - Good Process + Bad Outcome  = BAD LUCK (Accept)
    - Bad Process  + Good Outcome = DUMB LUCK (Trap - Avoid)
    - Bad Process  + Bad Outcome  = POOR JUDGMENT (Learn)
    """
    
    def __init__(self):
        self.logger = logging.getLogger("DecisionQuality")
        
    def analyze(self, trade: JournalEntry) -> dict:
        """
        Analyze a completed trade.
        Returns {grade, score, notes, category}
        """
        process_score = 0
        notes = []
        
        # 1. Setup Quality (50%)
        if trade.confidence >= 0.7:
            process_score += 50
            notes.append("High Confidence Setup")
        elif trade.confidence >= 0.5:
            process_score += 30
            notes.append("Medium Confidence")
        else:
            notes.append("Low Confidence Entry")
            
        # 2. Risk Management (30%)
        # Did we have a Stop Loss?
        if trade.stop_loss > 0:
            process_score += 30
            notes.append("Stop Loss Defined")
        else:
            # Only acceptable for some strategies, but generally bad
            notes.append("Missing Stop Loss")
            
        # 3. Rule Adherence (20%) - Simulated check
        # If exit reason was 'STOP' or 'TARGET', it means we followed the plan.
        # If 'FORCE', we panic exited.
        if trade.exit_reason in ["TARGET", "STOP", "SIGNAL"]:
            process_score += 20
            notes.append("Followed Exit Rules")
        elif trade.exit_reason == "FORCE":
            process_score -= 10
            notes.append("Forced Exit (Panic/Margin)")
            
        # Determine Outcome
        is_win = trade.pnl > 0
        
        # Categorize
        category = "UNKNOWN"
        grade = "C"
        
        if process_score >= 80:
            if is_win:
                category = "SKILL"
                grade = "A"
            else:
                category = "BAD_LUCK" # Good process, bad result
                grade = "B" # Still a good grade for process
        elif process_score < 50:
            if is_win:
                category = "DUMB_LUCK" # The most dangerous
                grade = "D" 
            else:
                category = "POOR_JUDGMENT"
                grade = "F"
        else:
            category = "AVERAGE"
            grade = "C"
            
        analysis = {
            "grade": grade,
            "score": process_score,
            "category": category,
            "notes": ", ".join(notes)
        }
        
        self.logger.info(f"🎓 Trade {trade.trade_id} Graded: {grade} ({category})")
        return analysis

# Singleton
decision_analytics = DecisionQuality()
