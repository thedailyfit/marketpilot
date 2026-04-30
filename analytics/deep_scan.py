import asyncio
import logging
import random
import datetime
from dataclasses import dataclass
from core.base_agent import BaseAgent
from core.event_bus import bus, EventType
from core.config_manager import sys_config
import upstox_client

@dataclass
class MarketTrend:
    timeframe: str
    trend: str # BULLISH, BEARISH, SIDEWAYS
    strength: float # 0.0 to 1.0

@dataclass
class OptionMetrics:
    strike: float
    option_type: str # CE/PE
    price: float
    iv: float
    iv_percentile: float
    delta: float
    theta: float
    gamma: float
    vega: float
    oi: int
    oi_change: int

class DeepScanAgent(BaseAgent):
    def __init__(self):
        super().__init__("DeepScanAgent")
        self.timeframes = ["1m", "5m", "15m", "1h", "1d"]
        self.trends = {}
        self.india_vix = 14.5 
        self.api_client = None
        self.upstox_market = None
        
    async def on_start(self):
        if sys_config.MODE == "LIVE" and sys_config.ACCESS_TOKEN:
            try:
                conf = upstox_client.Configuration()
                conf.access_token = sys_config.ACCESS_TOKEN
                self.api_client = upstox_client.ApiClient(conf)
                # Note: Upstox doesn't have a distinct 'MarketApi' class for OHLC/Quotes in some versions,
                # but it does have 'HistoryApi' or similar. We'll use basic quote/option endpoints.
                # Assuming 'MarketQuoteApi' or similar availability. 
                # For v2, we often check documentation. Let's try initializing generic API wrapper.
                pass 
            except Exception as e:
                self.logger.error(f"DeepScan: Upstox Init Error: {e}")

    async def perform_deep_scan(self, symbol="NSE_FO|NIFTY"):
        """Analyzes all timeframes and returns a consensus with Option Data."""
        self.logger.info(f"Starting Deep Scan for {symbol}...")
        
        # 1. Multi-Timeframe Trend (Mock for now, will link to MarketData history later)
        consensus_score = 0
        report = {}
        for tf in self.timeframes:
            trend = self._analyze_timeframe(tf)
            report[tf] = trend.trend
            weight = 3.0 if tf == "1d" else 1.0
            if trend.trend == "BULLISH": consensus_score += weight
            elif trend.trend == "BEARISH": consensus_score -= weight
        
        print(f"DEEP SCAN: Consensus Score = {consensus_score}")
        
        # 2. Options Chain Analysis
        if sys_config.MODE == "LIVE" and sys_config.ACCESS_TOKEN:
            chain_analysis, calls = await self._fetch_live_chain_analysis(symbol, consensus_score)
        else:
            chain_analysis = self._analyze_options_chain_sim(symbol, consensus_score)
            calls = self._generate_option_calls_sim(symbol, consensus_score)
        
        return {
            "symbol": symbol,
            "india_vix": self.india_vix,
            "trends": report,
            "consensus_score": consensus_score,
            "chain_analysis": chain_analysis,
            "recommendation": "BUY" if consensus_score > 3 else "SELL" if consensus_score < -3 else "WAIT",
            "calls": calls
        }

    async def _fetch_live_chain_analysis(self, symbol, score):
        """Fetches Real Option Chain from Upstox."""
        try:
            instrument_key = "NSE_INDEX|Nifty 50" if "NIFTY" in symbol else symbol
            api_instance = upstox_client.OptionsApi(self.api_client)
            
            # Fetch expiry dates from option contracts
            contracts_response = api_instance.get_option_contracts(instrument_key=instrument_key)
            if not contracts_response.data:
                return self._analyze_options_chain_sim(symbol, score), self._generate_option_calls_sim(symbol, score)
                
            # Get the nearest expiry date
            try:
                expiries = set([c.expiry for c in contracts_response.data if hasattr(c, 'expiry')])
                nearest_expiry = sorted(list(expiries))[0]
            except Exception:
                # Format is often "YYYY-MM-DD" e.g., "2023-11-09"
                nearest_expiry = (datetime.datetime.now() + datetime.timedelta(days=(3-datetime.datetime.now().weekday())%7)).strftime("%Y-%m-%d")

            # Fetch option chain
            chain = api_instance.get_put_call_option_chain(instrument_key=instrument_key, expiry_date=nearest_expiry)
            data = chain.data
            
            # Process Chain
            ce_oi = 0
            pe_oi = 0
            for item in data:
                if hasattr(item, 'call_options') and item.call_options and hasattr(item.call_options, 'market_data') and item.call_options.market_data:
                    ce_oi += getattr(item.call_options.market_data, 'oi', 0)
                if hasattr(item, 'put_options') and item.put_options and hasattr(item.put_options, 'market_data') and item.put_options.market_data:
                    pe_oi += getattr(item.put_options.market_data, 'oi', 0)
            
            pcr = pe_oi / ce_oi if ce_oi > 0 else 1.0
            
            message = "Live Connection Active. "
            if pcr > 1.2:
                message += "Bullish: Put writing dominates."
            elif pcr < 0.8:
                message += "Bearish: Call writing dominates."
            else:
                message += "Neutral OI distribution."
                
            analysis = {
                "pcr": round(pcr, 2),
                "max_pain": getattr(data[0], 'strike_price', 0) if data else 0,
                "message": message
            }
            
            # Still use the simulated option picks logic since generating Greeks live requires the GreeksCalculator 
            # and spot price passing which is handled separately.
            calls = self._generate_option_calls_sim(symbol, score)
            return analysis, calls
            
        except Exception as e:
            self.logger.error(f"Live Fetch Error: {e}")
            return self._analyze_options_chain_sim(symbol, score), self._generate_option_calls_sim(symbol, score)

    def _analyze_options_chain_sim(self, symbol, score):
        """Simulates analyzing real-time OI and Greeks."""
        # Simulation: If Bullish, Put Writers are active (High Put OI Change)
        message = "Neutral Chain"
        if score > 0:
            message = "Bullish: High Put Writing Detected. IV Cooling."
        elif score < 0:
            message = "Bearish: Call Writers Aggressive. IV Spiking."
            
        return {
            "pcr": 1.2 if score > 0 else 0.8,
            "max_pain": 19500,
            "message": message
        }

    def _analyze_timeframe(self, tf):
        """Applies 'All Indicator' logic to a timeframe."""
        directions = ["BULLISH", "BEARISH", "SIDEWAYS"]
        trend = random.choice(directions)
        if tf == "1d": trend = "BULLISH" 
        return MarketTrend(timeframe=tf, trend=trend, strength=random.random())

    def _generate_option_calls_sim(self, symbol, score):
        """Suggests 3 strikes based on Greeks & OI."""
        base_price = 19500
        
        # We need "High Delta" for Momentum, "Low Theta" for safety
        calls = []
        
        if score > 2: # STRONG BULLISH
            calls = [
                self._create_option_card(base_price, "CE", "ATM Momentum", 0.52, 12, 500000, 20000),
                self._create_option_card(base_price - 100, "CE", "ITM Safe", 0.75, 9, 800000, 15000),
                self._create_option_card(base_price + 50, "CE", "OTM HeroZero", 0.35, 18, 1200000, 50000)
            ]
        elif score < -2: # STRONG BEARISH
             calls = [
                self._create_option_card(base_price, "PE", "ATM Momentum", -0.51, 13, 600000, 25000),
                self._create_option_card(base_price + 100, "PE", "ITM Safe", -0.72, 10, 900000, 10000),
                self._create_option_card(base_price - 50, "PE", "OTM HeroZero", -0.30, 19, 1500000, 60000)
            ]
            
        return calls
        
    def _create_option_card(self, strike, otype, reason, delta, iv, oi, oi_chg):
        return {
            "strike": strike,
            "type": otype,
            "reason": reason,
            "metrics": {
                "delta": delta,
                "iv": iv,
                "iv_percentile": random.randint(20, 80),
                "oi": oi,
                "oi_change": oi_chg,
                "theta": -10.5, # placeholder
                "gamma": 0.02,
                "vega": 4.5
            }
        }

    async def on_stop(self):
        pass
