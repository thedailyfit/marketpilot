import random
import logging
import sqlite3
import asyncio
from typing import List, Dict
from core.base_agent import BaseAgent

logger = logging.getLogger("GeneticOptimizer")

class GeneticOptimizer(BaseAgent):
    """
    Finds the 'Golden Parameters' using Darwinian Evolution.
    Evolves [RSI_PERIOD, SL_PCT, TP_PCT] to maximize Net Profit.
    """
    
    def __init__(self):
        super().__init__("GeneticOptimizer")
        self.db_path = "data/market_data.db"
        self.population_size = 30
        self.generations = 10
        self.top_performers = 5
        self.best_config = None
        self.is_optimizing = False

    async def on_start(self):
        """Called by Supervisor on startup."""
        logger.info("🧬 GeneticOptimizer Agent Initialized (Standby Mode)")

    async def on_stop(self):
        """Called by Supervisor on shutdown."""
        self.is_optimizing = False
        logger.info("🧬 GeneticOptimizer Agent Stopped")

    async def run_optimization(self) -> Dict:
        """Run the full genetic evolution cycle."""
        if self.is_optimizing:
            return {"status": "Already Running", "best_config": self.best_config}
            
        self.is_optimizing = True
        logger.info("🧬 Starting Genetic Optimization...")
        
        try:
            # 1. Load Data
            data_rows = self._load_data()
            if not data_rows or len(data_rows) < 100:
                # If no data, use mock data size for simulation
                logger.warning("Insufficient Real Data. Using Mock Simulation Mode.")
                data_rows = list(range(1000)) # Placeholder

            # 2. Initialize Population
            population = self._create_initial_population()
            
            # 3. Evolution Loop
            for gen in range(self.generations):
                logger.info(f"🧬 Generation {gen+1}/{self.generations} Evolving...")
                
                # Evaluate Fitness
                scores = []
                for genome in population:
                    profit, win_rate = self._backtest(genome, data_rows)
                    scores.append((profit, genome))
                
                # Sort by Profit (Fitness Function)
                scores.sort(key=lambda x: x[0], reverse=True)
                
                # Select Top Performers
                survivors = [s[1] for s in scores[:self.top_performers]]
                self.best_config = survivors[0]
                
                # Create Next Generation (Crossover & Mutation)
                population = self._breed_next_gen(survivors)
                
                # Yield control to event loop
                await asyncio.sleep(0.1)
                
            logger.info(f"🏆 Optimization Complete. Best: {self.best_config}")
            self.is_optimizing = False
            
            return {
                "status": "Success",
                "best_config": self.best_config,
                "max_profit": scores[0][0],
                "generations": self.generations
            }
            
        except Exception as e:
            self.is_optimizing = False
            logger.error(f"Optimization Failed: {e}")
            return {"status": "Error", "message": str(e)}

    def _load_data(self) -> List:
        """Load ticks from DB."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Limit to recent 5000 ticks for speed
            cursor.execute("SELECT * FROM market_ticks ORDER BY timestamp DESC LIMIT 5000")
            rows = cursor.fetchall()
            conn.close()
            return rows
        except:
            return []

    def _create_initial_population(self) -> List[Dict]:
        """Generate random genomes."""
        pop = []
        for _ in range(self.population_size):
            pop.append({
                "rsi_period": random.randint(7, 21),
                "sl_pct": round(random.uniform(0.5, 2.0), 2),
                "tp_pct": round(random.uniform(1.0, 4.0), 2)
            })
        return pop

    def _backtest(self, genome, data) -> tuple:
        """Fast vectorized backtest simulation."""
        # Mock logic for MVP (Real backtest would compute indicators on DF)
        
        item = genome
        rsi_delta = abs(item['rsi_period'] - 14)
        sl_score = 1.0 if 0.8 <= item['sl_pct'] <= 1.2 else 0.5
        tp_score = 1.0 if 1.8 <= item['tp_pct'] <= 2.2 else 0.5
        
        # Add randomness
        noise = random.uniform(0.9, 1.1)
        
        profit = (100 - rsi_delta * 5) * sl_score * tp_score * noise
        win_rate = 60 * noise
        
        return profit, win_rate

    def _breed_next_gen(self, survivors: List[Dict]) -> List[Dict]:
        """Crossover and Mutation."""
        next_gen = survivors[:] # Keep elites
        
        while len(next_gen) < self.population_size:
            # Select parents
            p1 = random.choice(survivors)
            p2 = random.choice(survivors)
            
            # Crossover
            child = {
                "rsi_period": p1['rsi_period'] if random.random() > 0.5 else p2['rsi_period'],
                "sl_pct": p1['sl_pct'] if random.random() > 0.5 else p2['sl_pct'],
                "tp_pct": p1['tp_pct'] if random.random() > 0.5 else p2['tp_pct']
            }
            
            # Mutation (10% chance)
            if random.random() < 0.1:
                child["rsi_period"] = random.randint(7, 21)
            
            next_gen.append(child)
            
        return next_gen

# Test
if __name__ == "__main__":
    opt = GeneticOptimizer()
    # Mock DF for testing
    res = asyncio.run(opt.run_optimization())
    print(res)
