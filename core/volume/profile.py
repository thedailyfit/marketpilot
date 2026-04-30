"""
Volume Profile Engine
Calculates Volume-at-Price distribution, POC, VAH, VAL.
"""
import logging
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

@dataclass
class PriceLevel:
    price: float
    volume: float
    is_poc: bool = False
    is_vah: bool = False
    is_val: bool = False
    is_hvn: bool = False
    is_lvn: bool = False

@dataclass
class ProfileResult:
    poc: float
    vah: float
    val: float
    levels: List[PriceLevel]
    total_volume: float

class VolumeProfile:
    """
    Calculates Volume Profile from Trade or Bar data.
    """
    def __init__(self, tick_size: float = 0.05):
        self.logger = logging.getLogger("VolumeProfile")
        self.tick_size = tick_size
        
    def calculate(self, data: pd.DataFrame, value_area_pct: float = 0.70) -> Optional[ProfileResult]:
        """
        Calculate Fixed Range Volume Profile.
        Expects DataFrame with 'close' and 'volume'.
        Using 'close' as proxy for price if tick data unavailable.
        """
        if data.empty:
            return None
            
        # 1. Bucket Volume by Price
        # Round prices to nearest tick/bin
        # dynamically adjust bin size if range is huge?
        # For Nifty (25000), 5 points bin might be better than 0.05
        price_min = data['low'].min()
        price_max = data['high'].max()
        price_range = price_max - price_min
        
        # Adaptive Bin Size
        bin_size = self.tick_size
        if price_range > 1000: bin_size = 5.0
        elif price_range > 100: bin_size = 1.0
        elif price_range > 10: bin_size = 0.5
        
        # We need to distribute volume of a candle across its range?
        # Simplification: Assign all volume to Close price (common approximation for bar data)
        # Better: Distribute uniformly between High and Low? 
        # Let's use Close for speed/simplicity in V1, or typical price (H+L+C)/3
        
        typical_price = (data['high'] + data['low'] + data['close']) / 3
        
        # Create bins
        bins = np.arange(
            np.floor(price_min / bin_size) * bin_size, 
            np.ceil(price_max / bin_size) * bin_size + bin_size, 
            bin_size
        )
        
        # Histogram
        # Using simple Close price association for now
        # Actually, let's use the typical price series
        vol_dist, bin_edges = np.histogram(typical_price, bins=bins, weights=data['volume'])
        
        if vol_dist.sum() == 0:
            return None
            
        # 2. Find POC (Point of Control)
        max_vol_idx = np.argmax(vol_dist)
        poc_price = (bin_edges[max_vol_idx] + bin_edges[max_vol_idx+1]) / 2
        total_volume = vol_dist.sum()
        
        # 3. Calculate Value Area (VAH, VAL)
        # Start at POC and expand out
        sorted_indices = np.argsort(vol_dist)[::-1] # indices of volumes sorted descending? No, that's not right.
        # We need to expand from POC index up/down based on two-pointer or greedy approach
        
        target_vol = total_volume * value_area_pct
        current_vol = vol_dist[max_vol_idx]
        
        up_idx = max_vol_idx
        down_idx = max_vol_idx
        
        while current_vol < target_vol:
            up_vol = 0
            down_vol = 0
            
            if up_idx + 1 < len(vol_dist):
                up_vol = vol_dist[up_idx + 1]
                
            if down_idx - 1 >= 0:
                down_vol = vol_dist[down_idx - 1]
                
            if up_vol == 0 and down_vol == 0:
                break
                
            # Greedy expansion: Pick the side with more volume
            if up_vol >= down_vol:
                up_idx += 1
                current_vol += up_vol
            else:
                down_idx -= 1
                current_vol += down_vol
                
        val_price = bin_edges[down_idx]
        vah_price = bin_edges[up_idx + 1] # Upper edge of the bin
        
        # 4. Construct Result Levels
        levels = []
        avg_vol = np.mean(vol_dist)
        
        for i, vol in enumerate(vol_dist):
            price = (bin_edges[i] + bin_edges[i+1]) / 2
            is_poc = (i == max_vol_idx)
            is_vah = (price >= vah_price - bin_size/2 and price <= vah_price + bin_size/2) # Approx
            is_val = (price >= val_price - bin_size/2 and price <= val_price + bin_size/2)
            
            # Simple HVN/LVN logic
            is_hvn = vol > (avg_vol * 1.5)
            # LVN: significantly lower than neighbors? 
            # Or just low volume? Let's say < 0.5 avg
            is_lvn = vol < (avg_vol * 0.5)
            
            levels.append(PriceLevel(price, vol, is_poc, is_vah, is_val, is_hvn, is_lvn))
            
        return ProfileResult(
            poc=poc_price,
            vah=vah_price,
            val=val_price,
            levels=levels,
            total_volume=total_volume
        )

# Singleton
volume_profile = VolumeProfile()
