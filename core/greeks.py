
import math

class GreeksCalculator:
    """
    Calculates Option Greeks using Black-Scholes measure.
    No external dependencies (scipy/numpy) to ensure portability.
    """
    
    def __init__(self, risk_free_rate=0.10):
        # India Risk Free Rate approx 10% (0.10)
        self.r = risk_free_rate

    def _pdf(self, x):
        """Probability Density Function for Standard Normal Distribution"""
        return math.exp(-x**2 / 2) / math.sqrt(2 * math.pi)

    def _cdf(self, x):
        """Cumulative Distribution Function for Standard Normal Distribution"""
        return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

    def calculate_d1_d2(self, S, K, T, sigma):
        """
        Calculate d1 and d2 parameters.
        S: Spot Price
        K: Strike Price
        T: Time to Expiry (in years)
        sigma: Implied Volatility (decimal, e.g. 0.20 for 20%)
        """
        if T <= 0 or sigma <= 0:
            return 0, 0
            
        d1 = (math.log(S / K) + (self.r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        return d1, d2

    def calculate_greeks(self, S, K, T, sigma, option_type="CE"):
        """
        Calculate Delta, Gamma, Theta, Vega, Rho.
        
        Args:
            S (float): Spot Price
            K (float): Strike Price
            T (float): Time to Expiry (years)
            sigma (float): Implied Volatility (decimal)
            option_type (str): "CE" (Call) or "PE" (Put)
            
        Returns:
            dict: {delta, gamma, theta, vega, rho}
        """
        # Safety checks
        if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
            return {
                "delta": 0.0, "gamma": 0.0, "theta": 0.0, 
                "vega": 0.0, "rho": 0.0
            }

        d1, d2 = self.calculate_d1_d2(S, K, T, sigma)
        
        # Cache common terms
        exp_rt = math.exp(-self.r * T)
        N_d1 = self._cdf(d1)
        N_d2 = self._cdf(d2)
        N_neg_d1 = self._cdf(-d1)
        N_neg_d2 = self._cdf(-d2)
        pdf_d1 = self._pdf(d1)
        
        greeks = {}
        
        # 1. Delta
        if option_type == "CE":
            greeks['delta'] = N_d1
        else:
            greeks['delta'] = N_d1 - 1
            
        # 2. Gamma (Same for Call & Put)
        greeks['gamma'] = pdf_d1 / (S * sigma * math.sqrt(T))
        
        # 3. Vega (Same for Call & Put) - Value is change per 1% vol change usually, 
        # but here returning raw BS Vega (change per 100% vol). 
        # Traders usually stick to raw or divide by 100. Let's return raw / 100 for "per 1% IV"
        greeks['vega'] = (S * math.sqrt(T) * pdf_d1) / 100.0
        
        # 4. Theta
        # Theta usually expressed as decay per DAY (divide by 365)
        term1 = -(S * sigma * pdf_d1) / (2 * math.sqrt(T))
        
        if option_type == "CE":
            term2 = -self.r * K * exp_rt * N_d2
            greeks['theta'] = (term1 + term2) / 365.0
        else:
            term2 = self.r * K * exp_rt * N_neg_d2
            greeks['theta'] = (term1 + term2) / 365.0
            
        # 5. Rho
        if option_type == "CE":
            greeks['rho'] = (K * T * exp_rt * N_d2) / 100.0
        else:
            greeks['rho'] = (-K * T * exp_rt * N_neg_d2) / 100.0
            
        return {k: round(v, 4) for k, v in greeks.items()}

# Global Instance
greeks_calculator = GreeksCalculator()

# Usage Example
if __name__ == "__main__":
    calc = GreeksCalculator()
    # Nifty 23500 CE, Spot 23450, 2 days to expiry, 15% IV
    res = calc.calculate_greeks(23450, 23500, 2/365, 0.15, "CE")
    print(f"Call Greeks: {res}")
