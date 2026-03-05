import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import numpy as np
from polygon_client import PolygonClient
from config import Config

logger = logging.getLogger(__name__)


class GapUpScreener:
    """Identifies gap-up candidates based on pre-market/opening gaps and volume analysis."""
    
    def __init__(self, polygon_client: PolygonClient, config: Config):
        self.polygon = polygon_client
        self.config = config
        
    def calculate_market_cap_at_time(
        self, 
        ticker: str, 
        price: float, 
        date: datetime
    ) -> Optional[float]:
        """
        Calculate market cap at a specific time to avoid look-ahead bias.
        Uses shares outstanding from the most recent date before the target date.
        
        Args:
            ticker: Stock ticker symbol
            price: Price at the time of calculation
            date: Date for market cap calculation
            
        Returns:
            Market cap in dollars, or None if data unavailable
        """
        try:
            # Get ticker details as of the date (not current details)
            details = self.polygon.get_ticker_details(ticker, date)
            
            if not details or 'results' not in details:
                return None
                
            shares_outstanding = details['results'].get('weighted_shares_outstanding')
            if not shares_outstanding:
                shares_outstanding = details['results'].get('share_class_shares_outstanding')
                
            if shares_outstanding and shares_outstanding > 0:
                market_cap = price * shares_outstanding
                return market_cap
                
            return None
            
        except Exception as e:
            logger.warning(f"Failed to calculate market cap for {ticker} on {date}: {e}")
            return None
    
    def get_average_volume(
        self, 
        ticker: str, 
        end_date: datetime, 
        lookback_days: int = 20
    ) -> Optional[float]:
        """
        Calculate average daily volume over a lookback period.
        
        Args:
            ticker: Stock ticker symbol
            end_date: End date for volume calculation (exclusive)
            lookback_days: Number of trading days to look back
            
        Returns:
            Average volume, or None if insufficient data
        """
        try:
            start_date = end_date - timedelta(days=lookback_days * 2)  # Account for weekends
            
            bars = self.polygon.get_aggregate_bars(
                ticker=ticker,
                multiplier=1,
                timespan='day',
                from_date=start_date.strftime('%Y-%m-%d'),
                to_date=(end_date - timedelta(days=1)).strftime('%Y-%m-%d')
            )
            
            if not bars or 'results' not in bars or not bars['results']:
                return None
                
            volumes = [bar['v'] for bar in bars['results'] if 'v' in bar]
            
            if len(volumes) < lookback_days // 2:  # Require at least half the data
                return None
                
            return float(np.mean(volumes))
            
        except Exception as e:
            logger.warning(f"Failed to get average volume for {ticker}: {e}")
            return None
    
    def get_previous_close(
        self, 
        ticker: str, 
        target_date: datetime
    ) -> Optional[float]:
        """
        Get the previous trading day's closing price.
        
        Args:
            ticker: Stock ticker symbol
            target_date: The date for which we want the previous close
            
        Returns:
            Previous close price, or None if unavailable
        """
        try:
            # Look back up to 10 days to find previous close
            start_date = target_date - timedelta(days=10)
            
            bars = self.polygon.get_aggregate_bars(
                ticker=ticker,
                multiplier=1,
                timespan='day',
                from_date=start_date.strftime('%Y-%m-%d'),
                to_date=(target_date - timedelta(days=1)).strftime('%Y-%m-%d')
            )
            
            if not bars or 'results' not in bars or not bars['results']:
                return None
                
            # Get the most recent bar before target_date
            sorted_bars = sorted(bars['results'], key=lambda x: x['t'], reverse=True)
            if sorted_bars:
                return float(sorted_bars[0]['c'])
                
            return None
            
        except Exception as e:
            logger.warning(f"Failed to get previous close for {ticker}: {e}")
            return None
    
    def get_opening_price(
        self, 
        ticker: str, 
        date: datetime
    ) -> Optional[Dict]:
        """
        Get the opening price and first minute's data for a trading day.
        
        Args:
            ticker: Stock ticker symbol
            date: Trading date
            
        Returns:
            Dict with open, high, low, close, volume for first minute, or None
        """
        try:
            # Get minute bars for the trading day
            date_str = date.strftime('%Y-%m-%d')
            
            bars = self.polygon.get_aggregate_bars(
                ticker=ticker,
                multiplier=1,
                timespan='minute',
                from_date=date_str,
                to_date=date_str,
                limit=10  # Get first few minutes
            )
            
            if not bars or 'results' not in bars or not bars['results']:
                return None
                
            # Get the first minute bar
            first_bar = sorted(bars['results'], key=lambda x: x['t'])[0]
            
            return {
                'open': float(first_bar['o']),
                'high': float(first_bar['h']),
                'low': float(first_bar['l']),
                'close': float(first_bar['c']),
                'volume': int(first_bar['v']),
                'timestamp': first_bar['t']
            }
            
        except Exception as e:
            logger.warning(f"Failed to get opening price for {ticker} on {date}: {e}")
            return None
    
    def calculate_gap_percentage(
        self, 
        previous_close: float, 
        opening_price: float
    ) -> float:
        """Calculate gap percentage."""
        if previous_close <= 0:
            return 0.0
        return ((opening_price - previous_close) / previous_close) * 100
    
    def calculate_volume_ratio(
        self, 
        current_volume: float, 
        average_volume: float
    ) -> float:
        """Calculate volume ratio vs average."""
        if average_volume <= 0:
            return 0.0
        return current_volume / average_volume
    
    def check_corporate_actions(
        self, 
        ticker: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Dict]:
        """
        Check for corporate actions (splits, reverse splits) in a date range.
        
        Args:
            ticker: Stock ticker symbol
            start_date: Start date for checking
            end_date: End date for checking
            
        Returns:
            List of corporate actions found
        """
        try:
            actions = self.polygon.get_stock_splits(
                ticker=ticker,
                from_date=start_date.strftime('%Y-%m-%d'),
                to_date=end_date.strftime('%Y-%m-%d')
            )
            
            if actions and 'results' in actions:
                return actions['results']
                
            return []
            
        except Exception as e:
            logger.warning(f"Failed to check corporate actions for {ticker}: {e}")
            return []
    
    def adjust_price_for_splits(
        self, 
        price: float, 
        splits: List[Dict], 
        reference_date: datetime
    ) -> float:
        """
        Adjust price for splits that occurred after reference_date.
        
        Args:
            price: Original price
            splits: List of split events
            reference_date: Date of the original price
            
        Returns:
            Adjusted price
        """
        adjusted_price = price
        
        for split in splits:
            split_date = datetime.fromtimestamp(split['execution_date'] / 1000)
            
            if split_date > reference_date:
                split_ratio = split.get('split_to', 1) / split.get('split_from', 1)
                adjusted_price *= split_ratio
                
        return adjusted_price
    
    def estimate_borrow_cost(
        self, 
        market_cap: float, 
        liquidity_score: float
    ) -> float:
        """
        Estimate hard-to-borrow cost based on market cap and liquidity.
        
        Args:
            market_cap: Market capitalization
            liquidity_score: Liquidity metric (volume ratio)
            
        Returns:
            Annual borrow cost rate (as decimal, e.g., 0.20 for 20%)
        """
        base_cost = self.config.DEFAULT_BORROW_COST
        
        # Higher cost for smaller market caps
        if market_cap < 50_000_000:
            base_cost += 0.30  # Additional 30% for micro caps
        elif market_cap < 300_000_000:
            base_cost += 0.15  # Additional 15% for small caps
            
        # Higher cost for less liquid stocks
        if liquidity_score < 0.5:
            base_cost += 0.20  # Additional 20% for very illiquid
        elif liquidity_score < 1.0:
            base_cost += 0.10  # Additional 10% for somewhat illiquid
            
        # Cap maximum borrow cost
        return min(base_cost, self.config.MAX_BORROW_COST)
    
    def estimate_slippage(
        self, 
        market_cap: float, 
        volume_ratio: float, 
        gap_percentage: float,
        position_size: float
    ) -> float:
        """
        Estimate slippage percentage for entry/exit based on liquidity and conditions.
        
        Args:
            market_cap: Market capitalization
            volume_ratio: Volume ratio vs average
            gap_percentage: Gap up percentage
            position_size: Dollar size of position
            
        Returns:
            Expected slippage as percentage (e.g., 0.02 for 2%)
        """
        base_slippage = self.config.BASE_SLIPPAGE
        
        # Higher slippage for smaller market caps
        if market_cap < 50_000_000:
            base_slippage += 0.03
        elif market_cap < 300_000_000:
            base_slippage += 0.015
            
        # Higher slippage for lower volume
        if volume_ratio < 0.5:
            base_slippage += 0.02
        elif volume_ratio < 1.0:
            base_slippage += 0.01
            
        # Higher slippage for larger gaps (more volatility)
        if gap_percentage > 50:
            base_slippage += 0.02
        elif gap_percentage > 30:
            base_slippage += 0.01
            
        # Position size impact (assuming typical ADV around $100k for small caps)
        estimated_adv = market_cap * 0.001  # Rough estimate
        if estimated_adv > 0:
            size_impact = (position_size / estimated_adv) * 0.05
            base_slippage += min(size_impact, 0.05)
            
        return min(base_slippage, self.config.MAX_SLIPPAGE)
    
    def check_availability_to_short(
        self, 
        ticker: str, 
        market_cap: float, 
        volume_ratio: float
    ) -> Tuple[bool, str]:
        """
        Estimate whether a stock would be available to short.
        
        Args:
            ticker: Stock ticker symbol
            market_cap: Market capitalization
            volume_ratio: Volume ratio vs average
            
        Returns:
            Tuple of (is_available, reason)
        """
        # Very small caps often unavailable
        if market_cap < self.config.MIN_MARKET_CAP:
            return False, f"Market cap ${market_cap:,.0f} below minimum"
            
        # Very illiquid stocks often unavailable
        if volume_ratio < 0.2:
            return False, "Insufficient liquidity"
            
        # Add probability-based unavailability for small caps
        if market_cap < 100_000_000:
            # Use ticker hash for deterministic but pseudo-random unavailability
            ticker_hash = hash(ticker) % 100
            unavailable_threshold = 30  # 30% of micro caps unavailable
            
            if ticker_hash < unavailable_threshold:
                return False, "Hard to borrow - unavailable"
                
        return True, "Available"
    
    def screen_ticker(
        self, 
        ticker: str, 
        date: datetime, 
        min_gap_pct: float = None,
        max_gap_pct: float = None,
        min_volume_ratio: float = None,
        max_market_cap: float = None
    ) -> Optional[Dict]:
        """
        Screen a single ticker for gap-up criteria on a specific date.
        
        Args:
            ticker: Stock ticker symbol
            date: Trading date to screen
            min_gap_pct: Minimum gap percentage (default from config)
            max_gap_pct: Maximum gap percentage (default from config)
            min_volume_ratio: Minimum volume ratio (default from config)
            max_market_cap: Maximum market cap (default from config)
            
        Returns:
            Dict with screening results and metadata, or None if doesn't qualify
        """
        # Use config defaults if not specified
        min_gap_pct = min_gap_pct or self.config.MIN_GAP_PERCENTAGE
        max_gap_pct = max_gap_pct or self.config.MAX_GAP_PERCENTAGE
        min_volume_ratio = min_volume_ratio or self.config.MIN_VOLUME_RATIO
        max_market_cap = max_market_cap or self.config.MAX_MARKET_CAP
        
        try:
            # Get previous close
            prev_close = self.get_previous_close(ticker, date)
            if prev_close is None:
                return None
                
            # Get opening data
            opening_data = self.get_opening_price(ticker, date)
            if opening_data is None:
                return None
                
            opening_price = opening_data['open']
            
            # Calculate gap percentage
            gap_pct = self.calculate_gap_percentage(prev_close, opening_price)
            
            # Check gap criteria
            if gap_pct < min_gap_pct or gap_pct > max_gap_pct:
                return None
                
            # Calculate market cap at entry time (avoid look-ahead bias)
            market_cap = self.calculate_market_cap_at_time(ticker, opening_price, date)
            if market_cap is None or market_cap > max_market_cap:
                return None
                
            # Get average volume
            avg_volume = self.get_average_volume(ticker, date, self.config.VOLUME_LOOKBACK_DAYS)
            if avg_volume is None:
                return None
                
            # Calculate volume ratio (using first minute volume as proxy for opening volume)
            volume_ratio = self.calculate_volume_ratio(opening_data['volume'], avg_volume / 390)  # avg per minute
            
            # Check volume criteria
            if volume_ratio < min_volume_ratio:
                return None
                
            # Check for corporate actions in recent history
            splits = self.check_corporate_actions(
                ticker, 
                date - timedelta(days=