"""
Option Chain Analyzer
Fetches live option chain data from Upstox and calculates PCR, Max Pain, OI analysis.
"""
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

try:
    from upstox_client import OptionApi
    from upstox_client.rest import ApiException
    HAS_UPSTOX = True
except ImportError:
    HAS_UPSTOX = False

from core.config_manager import sys_config


logger = logging.getLogger(__name__)


@dataclass
class OptionData:
    """Single option contract data."""
    strike_price: float
    expiry: str
    option_type: str  # "CE" or "PE"
    ltp: float
    oi: int
    oi_change: int
    volume: int
    iv: float
    delta: float = 0.0
    theta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0


@dataclass 
class OptionChainAnalysis:
    """Complete option chain analysis result."""
    symbol: str
    spot_price: float
    expiry: str
    pcr: float  # Put-Call Ratio
    max_pain: float
    total_ce_oi: int
    total_pe_oi: int
    highest_ce_oi_strike: float
    highest_pe_oi_strike: float
    support_level: float  # Based on PE OI
    resistance_level: float  # Based on CE OI
    iv_percentile: float
    timestamp: datetime


class OptionChainAnalyzer:
    """
    Analyzes option chain for trading decisions.
    Works with Upstox API or simulated data.
    """
    
    def __init__(self):
        self.cache: Dict[str, OptionChainAnalysis] = {}
        self.cache_ttl = 60  # 60 seconds cache
        self.last_fetch: Dict[str, float] = {}
        
        # Weekly expiry calendar for Indian indices
        self.weekly_expiry = {
            0: "MIDCPNIFTY",  # Monday
            1: "FINNIFTY",    # Tuesday
            2: "BANKNIFTY",   # Wednesday
            3: "NIFTY",       # Thursday
            4: None,          # Friday (no weekly expiry)
            5: None,          # Saturday
            6: None           # Sunday
        }
        
    def get_current_expiry_symbol(self) -> Optional[str]:
        """Get which index expires today."""
        today = datetime.now().weekday()
        return self.weekly_expiry.get(today)
    
    def get_next_expiry_date(self, symbol: str = "NIFTY") -> datetime:
        """Calculate next expiry date for a symbol."""
        now = datetime.now()
        
        # Map symbol to expiry day
        expiry_days = {
            "NIFTY": 3,       # Thursday
            "BANKNIFTY": 2,   # Wednesday
            "FINNIFTY": 1,    # Tuesday
            "MIDCPNIFTY": 0   # Monday
        }
        
        target_day = expiry_days.get(symbol.upper(), 3)
        days_ahead = target_day - now.weekday()
        
        if days_ahead <= 0:  # Target day already passed this week
            days_ahead += 7
        
        return now + timedelta(days=days_ahead)
    
    async def fetch_option_chain(self, symbol: str = "NIFTY") -> Optional[List[OptionData]]:
        """
        Fetch live option chain from Upstox API.
        Falls back to simulated data if API unavailable.
        """
        if not HAS_UPSTOX or not sys_config.ACCESS_TOKEN:
            logger.warning("Upstox API not available. Using simulated option chain.")
            return self._simulate_option_chain(symbol)
        
        try:
            from upstox_client import Configuration, ApiClient
            
            config = Configuration()
            config.access_token = sys_config.ACCESS_TOKEN
            
            api_client = ApiClient(config)
            option_api = OptionApi(api_client)
            
            # 1. Resolve Instrument Key (e.g. NSE_INDEX|Nifty 50)
            instrument_key = f"NSE_INDEX|{symbol}"
            if "NIFTY" in symbol.upper() and "|" not in symbol:
                if "BANK" in symbol.upper(): instrument_key = "NSE_INDEX|Nifty Bank"
                else: instrument_key = "NSE_INDEX|Nifty 50"

            # 2. Get Expiry
            expiry = self.get_next_expiry_date(symbol).strftime("%Y-%m-%d")
            
            # 3. Fetch Real Chain
            logger.info(f"Fetching real Option Chain for {instrument_key} expiring {expiry}")
            response = option_api.get_put_call_option_chain(instrument_key, expiry)
            
            if response.status == "success" and response.data:
                return self._parse_upstox_chain(response.data)
            else:
                logger.error(f"Upstox Chain Error: {response.status}")
                return self._simulate_option_chain(symbol)
            
        except Exception as e:
            logger.error(f"Error fetching option chain: {e}")
            return self._simulate_option_chain(symbol)

    def _parse_upstox_chain(self, strike_data_list) -> List[OptionData]:
        """Converts Upstox OptionStrikeData list to our internal OptionData list."""
        parsed = []
        for strike in strike_data_list:
            # Handle CE
            if strike.call_options:
                co = strike.call_options
                parsed.append(OptionData(
                    strike_price=strike.strike_price,
                    expiry=strike.expiry.strftime("%Y-%m-%d") if hasattr(strike.expiry, "strftime") else str(strike.expiry),
                    option_type="CE",
                    ltp=co.market_data.ltp if co.market_data else 0,
                    oi=co.market_data.oi if co.market_data else 0,
                    oi_change=0, # Upstox API v2 doesn't directly give 1-day change in this call usually
                    volume=0,
                    iv=co.greeks.iv if co.greeks else 0,
                    delta=co.greeks.delta if co.greeks else 0,
                    theta=co.greeks.theta if co.greeks else 0,
                    gamma=co.greeks.gamma if co.greeks else 0,
                    vega=co.greeks.vega if co.greeks else 0
                ))
            # Handle PE
            if strike.put_options:
                po = strike.put_options
                parsed.append(OptionData(
                    strike_price=strike.strike_price,
                    expiry=strike.expiry.strftime("%Y-%m-%d") if hasattr(strike.expiry, "strftime") else str(strike.expiry),
                    option_type="PE",
                    ltp=po.market_data.ltp if po.market_data else 0,
                    oi=po.market_data.oi if po.market_data else 0,
                    oi_change=0,
                    volume=0,
                    iv=po.greeks.iv if po.greeks else 0,
                    delta=po.greeks.delta if po.greeks else 0,
                    theta=po.greeks.theta if po.greeks else 0,
                    gamma=po.greeks.gamma if po.greeks else 0,
                    vega=po.greeks.vega if po.greeks else 0
                ))
        return parsed
    
    def _simulate_option_chain(self, symbol: str) -> List[OptionData]:
        """Generate simulated option chain for testing."""
        import random
        
        # Simulated spot prices
        spot_prices = {
            "NIFTY": 23500,
            "BANKNIFTY": 49000,
            "FINNIFTY": 24000,
            "MIDCPNIFTY": 12500
        }
        
        spot = spot_prices.get(symbol, 23500)
        expiry = self.get_next_expiry_date(symbol).strftime("%Y-%m-%d")
        
        options = []
        
        # Generate strikes around spot price
        step = 50 if symbol == "NIFTY" else 100
        
        for i in range(-10, 11):
            strike = round(spot + (i * step), -1)
            
            # Call option
            ce_oi = random.randint(50000, 500000)
            ce_premium = max(10, spot - strike + random.randint(50, 200)) if strike < spot else random.randint(10, 100)
            
            options.append(OptionData(
                strike_price=strike,
                expiry=expiry,
                option_type="CE",
                ltp=ce_premium,
                oi=ce_oi,
                oi_change=random.randint(-50000, 50000),
                volume=random.randint(10000, 100000),
                iv=random.uniform(10, 25)
            ))
            
            # Put option
            pe_oi = random.randint(50000, 500000)
            pe_premium = max(10, strike - spot + random.randint(50, 200)) if strike > spot else random.randint(10, 100)
            
            options.append(OptionData(
                strike_price=strike,
                expiry=expiry,
                option_type="PE",
                ltp=pe_premium,
                oi=pe_oi,
                oi_change=random.randint(-50000, 50000),
                volume=random.randint(10000, 100000),
                iv=random.uniform(10, 25)
            ))
        
        return options
    
    def calculate_pcr(self, options: List[OptionData]) -> float:
        """Calculate Put-Call Ratio based on Open Interest."""
        total_pe_oi = sum(o.oi for o in options if o.option_type == "PE")
        total_ce_oi = sum(o.oi for o in options if o.option_type == "CE")
        
        if total_ce_oi == 0:
            return 1.0
        
        return round(total_pe_oi / total_ce_oi, 2)
    
    def calculate_max_pain(self, options: List[OptionData], spot_price: float) -> float:
        """
        Calculate Max Pain strike - where option writers have maximum profit.
        This is where buyers lose most money at expiry.
        """
        strikes = set(o.strike_price for o in options)
        
        pain_values = {}
        
        for test_strike in strikes:
            total_pain = 0
            
            for option in options:
                if option.option_type == "CE":
                    # Call buyers lose if price below strike
                    if test_strike < option.strike_price:
                        total_pain += option.oi * 0  # OTM, no loss
                    else:
                        total_pain += option.oi * (test_strike - option.strike_price)
                else:  # PE
                    # Put buyers lose if price above strike  
                    if test_strike > option.strike_price:
                        total_pain += option.oi * 0  # OTM, no loss
                    else:
                        total_pain += option.oi * (option.strike_price - test_strike)
            
            pain_values[test_strike] = total_pain
        
        # Max pain is where total pain is minimum for option buyers
        # (i.e., where option writers make most money)
        if not pain_values:
            return spot_price
        
        max_pain_strike = min(pain_values, key=pain_values.get)
        return max_pain_strike
    
    def find_support_resistance(self, options: List[OptionData]) -> Tuple[float, float]:
        """
        Find support and resistance based on OI.
        - High PE OI = Support (put writers don't want price to go below)
        - High CE OI = Resistance (call writers don't want price to go above)
        """
        pe_oi_by_strike = {}
        ce_oi_by_strike = {}
        
        for option in options:
            if option.option_type == "PE":
                pe_oi_by_strike[option.strike_price] = option.oi
            else:
                ce_oi_by_strike[option.strike_price] = option.oi
        
        # Highest PE OI = Strong support
        support = max(pe_oi_by_strike, key=pe_oi_by_strike.get) if pe_oi_by_strike else 0
        
        # Highest CE OI = Strong resistance
        resistance = max(ce_oi_by_strike, key=ce_oi_by_strike.get) if ce_oi_by_strike else 0
        
        return support, resistance
    
    async def analyze(self, symbol: str = "NIFTY", spot_price: float = 0) -> OptionChainAnalysis:
        """
        Complete option chain analysis.
        """
        # Check cache
        cache_key = f"{symbol}_{datetime.now().strftime('%Y%m%d%H%M')}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Fetch option chain
        options = await self.fetch_option_chain(symbol)
        
        if not options:
            return self._default_analysis(symbol)
        
        # Calculate metrics
        pcr = self.calculate_pcr(options)
        
        # Get spot price from config or estimate
        if spot_price == 0:
            spot_price = 23500 if symbol == "NIFTY" else 49000
        
        max_pain = self.calculate_max_pain(options, spot_price)
        support, resistance = self.find_support_resistance(options)
        
        # OI totals
        total_ce_oi = sum(o.oi for o in options if o.option_type == "CE")
        total_pe_oi = sum(o.oi for o in options if o.option_type == "PE")
        
        # Highest OI strikes
        ce_options = [o for o in options if o.option_type == "CE"]
        pe_options = [o for o in options if o.option_type == "PE"]
        
        highest_ce_oi_strike = max(ce_options, key=lambda x: x.oi).strike_price if ce_options else 0
        highest_pe_oi_strike = max(pe_options, key=lambda x: x.oi).strike_price if pe_options else 0
        
        # Average IV
        avg_iv = sum(o.iv for o in options) / len(options) if options else 15.0
        
        analysis = OptionChainAnalysis(
            symbol=symbol,
            spot_price=spot_price,
            expiry=self.get_next_expiry_date(symbol).strftime("%Y-%m-%d"),
            pcr=pcr,
            max_pain=max_pain,
            total_ce_oi=total_ce_oi,
            total_pe_oi=total_pe_oi,
            highest_ce_oi_strike=highest_ce_oi_strike,
            highest_pe_oi_strike=highest_pe_oi_strike,
            support_level=support,
            resistance_level=resistance,
            iv_percentile=avg_iv,
            timestamp=datetime.now()
        )
        
        # Cache result
        self.cache[cache_key] = analysis
        
        return analysis
    
    def _default_analysis(self, symbol: str) -> OptionChainAnalysis:
        """Return default analysis when data unavailable."""
        return OptionChainAnalysis(
            symbol=symbol,
            spot_price=23500 if symbol == "NIFTY" else 49000,
            expiry=self.get_next_expiry_date(symbol).strftime("%Y-%m-%d"),
            pcr=1.0,
            max_pain=23500,
            total_ce_oi=0,
            total_pe_oi=0,
            highest_ce_oi_strike=0,
            highest_pe_oi_strike=0,
            support_level=0,
            resistance_level=0,
            iv_percentile=15.0,
            timestamp=datetime.now()
        )
    
    def get_trading_bias(self, analysis: OptionChainAnalysis) -> str:
        """
        Determine trading bias based on option chain analysis.
        
        Returns:
            "BULLISH", "BEARISH", or "NEUTRAL"
        """
        bias_score = 0
        
        # PCR analysis
        # PCR > 1.2 = Bullish (more puts written = support)
        # PCR < 0.8 = Bearish (more calls written = resistance)
        if analysis.pcr > 1.2:
            bias_score += 2
        elif analysis.pcr < 0.8:
            bias_score -= 2
        elif analysis.pcr > 1.0:
            bias_score += 1
        elif analysis.pcr < 1.0:
            bias_score -= 1
        
        # Max Pain analysis
        # If spot > max pain, bearish pull towards max pain
        # If spot < max pain, bullish pull towards max pain
        if analysis.spot_price > analysis.max_pain:
            bias_score -= 1
        elif analysis.spot_price < analysis.max_pain:
            bias_score += 1
        
        # Support/Resistance proximity
        distance_to_support = abs(analysis.spot_price - analysis.support_level)
        distance_to_resistance = abs(analysis.spot_price - analysis.resistance_level)
        
        if distance_to_support < distance_to_resistance:
            bias_score += 1  # Closer to support = bullish
        else:
            bias_score -= 1  # Closer to resistance = bearish
        
        # Determine final bias
        if bias_score >= 2:
            return "BULLISH"
        elif bias_score <= -2:
            return "BEARISH"
        else:
            return "NEUTRAL"


# Global instance
option_analyzer = OptionChainAnalyzer()
