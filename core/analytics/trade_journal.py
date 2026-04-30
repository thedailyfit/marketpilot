"""
Auto Trade Journal
Records the lifecycle of every trade for analysis.
"""
import logging
import json
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime

@dataclass
class JournalEntry:
    """A single trade record."""
    trade_id: str
    timestamp: int
    symbol: str
    action: str
    strategy: str
    
    # Context (The "Why")
    regime: str
    vix: float
    fragility: float
    confidence: float
    setup_name: str
    
    # Execution (The "How")
    entry_price: float
    quantity: int
    stop_loss: float
    take_profit: float
    
    # Outcome (The Result) - Updated on exit
    exit_price: float = 0.0
    exit_time: int = 0
    pnl: float = 0.0
    pnl_percent: float = 0.0
    exit_reason: str = "OPEN" # TARGET, STOP, TIME, SIGNAL, FORCE
    
    # Analysis (The Lesson) - Updated by DecisionQuality
    grade: str = "PENDING"   # A, B, C, F
    quality_score: int = 0   # 0-100
    review_notes: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)

class TradeJournal:
    """
    Central database of all trades.
    Persists to JSON for analysis.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("TradeJournal")
        self.data_path = Path("data/journal/trades.json")
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self.trades: List[JournalEntry] = []
        self._load()
        
    def log_entry(self, 
                  symbol: str, 
                  action: str, 
                  strategy: str,
                  quantity: int,
                  price: float,
                  sl: float,
                  tp: float,
                  context: Dict) -> str:
        """
        Log a NEW trade entry.
        Returns trade_id.
        """
        trade_id = str(uuid.uuid4())[:8]
        
        entry = JournalEntry(
            trade_id=trade_id,
            timestamp=int(datetime.now().timestamp()),
            symbol=symbol,
            action=action,
            strategy=strategy,
            quantity=quantity,
            entry_price=price,
            stop_loss=sl,
            take_profit=tp,
            # Context unpacking
            regime=context.get("regime", "UNKNOWN"),
            vix=context.get("vix", 0.0),
            fragility=context.get("fragility", 0.0),
            confidence=context.get("confidence", 0.0),
            setup_name=context.get("setup", "MANUAL")
        )
        
        self.trades.append(entry)
        self._save()
        self.logger.info(f"📝 Journaled Trade: {symbol} ({action}) ID: {trade_id}")
        return trade_id
        
    def log_exit(self, trade_id: str, exit_price: float, reason: str):
        """
        Update an existing trade with EXIT details.
        """
        trade = self.get_trade(trade_id)
        if not trade:
            self.logger.error(f"Trade ID {trade_id} not found for exit.")
            return
            
        trade.exit_price = exit_price
        trade.exit_time = int(datetime.now().timestamp())
        trade.exit_reason = reason
        
        # Calc PnL
        if trade.action == "BUY":
            trade.pnl = (exit_price - trade.entry_price) * trade.quantity
            trade.pnl_percent = ((exit_price - trade.entry_price) / trade.entry_price) * 100
        else: # SELL
            trade.pnl = (trade.entry_price - exit_price) * trade.quantity
            trade.pnl_percent = ((trade.entry_price - exit_price) / trade.entry_price) * 100
            
        self._save()
        self.logger.info(f"🏁 Closed Trade: {trade_id} PnL: {trade.pnl:.2f} ({trade.pnl_percent:.2f}%)")
        
    def update_analysis(self, trade_id: str, grade: str, score: int, notes: str):
        """
        Update qualitative analysis (Grades).
        """
        trade = self.get_trade(trade_id)
        if trade:
            trade.grade = grade
            trade.quality_score = score
            trade.review_notes = notes
            self._save()

    def get_trade(self, trade_id: str) -> Optional[JournalEntry]:
        for t in self.trades:
            if t.trade_id == trade_id:
                return t
        return None
        
    def get_all_trades(self) -> List[JournalEntry]:
        return self.trades

    def _save(self):
        try:
            with open(self.data_path, 'w') as f:
                json.dump([t.to_dict() for t in self.trades], f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save journal: {e}")

    def _load(self):
        if not self.data_path.exists():
            return
        try:
            with open(self.data_path, 'r') as f:
                data = json.load(f)
                self.trades = [JournalEntry(**d) for d in data]
        except Exception as e:
            self.logger.error(f"Failed to load journal: {e}")

# Singleton
trade_journal = TradeJournal()
