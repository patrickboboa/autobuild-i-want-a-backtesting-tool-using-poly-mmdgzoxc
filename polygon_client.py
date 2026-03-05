import os
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class PolygonClient:
    """
    Polygon.io API wrapper for fetching market data with rate limit management.
    Handles ticker screening, market cap filtering, historical data, and splits/corporate actions.
    """
    
    BASE_URL = "https://api.polygon.io"
    
    def __init__(self, api_key: Optional[str] = None, max_retries: int = 3):
        """
        Initialize Polygon API client.
        
        Args:
            api_key: Polygon API key (if None, reads from POLYGON_API_KEY env var)
            max_retries: Maximum number of retry attempts for failed requests
        """
        self.api_key = api_key or os.getenv('POLYGON_API_KEY')
        if not self.api_key:
            raise ValueError("Polygon API key not provided and POLYGON_API_KEY env var not set")
        
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        self.last_request_time = 0
        self.min_request_interval = 0  # No rate limiting for premium unlimited
        
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """
        Make API request with error handling.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            JSON response as dictionary
        """
        if params is None:
            params = {}
        
        params['apiKey'] = self.api_key
        
        # Rate limiting (though unlimited for premium)
        if self.min_request_interval > 0:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.min_request_interval:
                time.sleep(self.min_request_interval - elapsed)
        
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            self.last_request_time = time.time()
            
            if response.status_code == 429:
                logger.warning("Rate limit hit, waiting 60 seconds")
                time.sleep(60)
                return self._make_request(endpoint, params)
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {endpoint}: {str(e)}")
            raise
    
    def get_ticker_details(self, ticker: str, date: Optional[str] = None) -> Optional[Dict]:
        """
        Get detailed ticker information including market cap at specific date.
        
        Args:
            ticker: Stock ticker symbol
            date: Date in YYYY-MM-DD format (if None, uses current date)
            
        Returns:
            Ticker details dictionary or None if not found
        """
        endpoint = f"/v3/reference/tickers/{ticker}"
        params = {}
        if date:
            params['date'] = date
        
        try:
            data = self._make_request(endpoint, params)
            return data.get('results')
        except Exception as e:
            logger.warning(f"Could not fetch ticker details for {ticker}: {str(e)}")
            return None
    
    def get_all_tickers(self, market: str = "stocks", active: bool = True, 
                       date: Optional[str] = None, limit: int = 1000) -> List[Dict]:
        """
        Get all tickers from Polygon, including delisted tickers to avoid survivorship bias.
        
        Args:
            market: Market type (default: "stocks")
            active: If True, only active tickers; if False, includes delisted
            date: Reference date for ticker universe
            limit: Results per page
            
        Returns:
            List of ticker dictionaries
        """
        endpoint = "/v3/reference/tickers"
        params = {
            'market': market,
            'active': active,
            'limit': limit
        }
        if date:
            params['date'] = date
        
        all_tickers = []
        next_url = None
        
        while True:
            try:
                if next_url:
                    response = self.session.get(next_url, timeout=30)
                    response.raise_for_status()
                    data = response.json()
                else:
                    data = self._make_request(endpoint, params)
                
                results = data.get('results', [])
                all_tickers.extend(results)
                
                next_url = data.get('next_url')
                if next_url:
                    next_url = f"{next_url}&apiKey={self.api_key}"
                else:
                    break
                    
            except Exception as e:
                logger.error(f"Error fetching tickers: {str(e)}")
                break
        
        logger.info(f"Retrieved {len(all_tickers)} tickers from Polygon")
        return all_tickers
    
    def get_market_cap(self, ticker: str, date: str) -> Optional[float]:
        """
        Calculate market cap at specific date using previous day's close and shares outstanding.
        This avoids look-ahead bias by using data available at entry time.
        
        Args:
            ticker: Stock ticker symbol
            date: Date in YYYY-MM-DD format
            
        Returns:
            Market cap in USD or None if unavailable
        """
        # Get ticker details for shares outstanding
        details = self.get_ticker_details(ticker, date)
        if not details:
            return None
        
        shares_outstanding = details.get('weighted_shares_outstanding') or details.get('share_class_shares_outstanding')
        if not shares_outstanding:
            return None
        
        # Get previous trading day's close price
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        # Go back up to 7 days to find previous close
        for days_back in range(1, 8):
            prev_date = date_obj - timedelta(days=days_back)
            prev_date_str = prev_date.strftime('%Y-%m-%d')
            
            bars = self.get_daily_bars(ticker, prev_date_str, prev_date_str)
            if bars and len(bars) > 0:
                close_price = bars[0].get('c')
                if close_price:
                    return shares_outstanding * close_price
        
        return None
    
    def get_daily_bars(self, ticker: str, from_date: str, to_date: str, 
                      adjusted: bool = True, limit: int = 50000) -> List[Dict]:
        """
        Get daily aggregated bars for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            adjusted: Whether to adjust for splits
            limit: Maximum number of results
            
        Returns:
            List of bar dictionaries with keys: o, h, l, c, v, vw, t, n
        """
        endpoint = f"/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}"
        params = {
            'adjusted': str(adjusted).lower(),
            'sort': 'asc',
            'limit': limit
        }
        
        try:
            data = self._make_request(endpoint, params)
            return data.get('results', [])
        except Exception as e:
            logger.error(f"Error fetching daily bars for {ticker}: {str(e)}")
            return []
    
    def get_minute_bars(self, ticker: str, date: str, 
                       adjusted: bool = True, limit: int = 50000) -> List[Dict]:
        """
        Get minute-level aggregated bars for a ticker on specific date.
        Essential for identifying gap-up and intraday entry/exit points.
        
        Args:
            ticker: Stock ticker symbol
            date: Date in YYYY-MM-DD format
            adjusted: Whether to adjust for splits
            limit: Maximum number of results
            
        Returns:
            List of bar dictionaries with keys: o, h, l, c, v, vw, t, n
        """
        endpoint = f"/v2/aggs/ticker/{ticker}/range/1/minute/{date}/{date}"
        params = {
            'adjusted': str(adjusted).lower(),
            'sort': 'asc',
            'limit': limit
        }
        
        try:
            data = self._make_request(endpoint, params)
            return data.get('results', [])
        except Exception as e:
            logger.error(f"Error fetching minute bars for {ticker}: {str(e)}")
            return []
    
    def get_quotes(self, ticker: str, timestamp: int) -> List[Dict]:
        """
        Get quotes (bid/ask) at or near specific timestamp.
        Critical for modeling bid-ask spreads on illiquid small caps.
        
        Args:
            ticker: Stock ticker symbol
            timestamp: Unix timestamp in milliseconds
            
        Returns:
            List of quote dictionaries
        """
        # Convert timestamp to date
        dt = datetime.fromtimestamp(timestamp / 1000)
        date = dt.strftime('%Y-%m-%d')
        
        endpoint = f"/v3/quotes/{ticker}"
        params = {
            'timestamp': timestamp,
            'order': 'asc',
            'limit': 10
        }
        
        try:
            data = self._make_request(endpoint, params)
            return data.get('results', [])
        except Exception as e:
            logger.warning(f"Error fetching quotes for {ticker}: {str(e)}")
            return []
    
    def get_splits(self, ticker: str, from_date: Optional[str] = None, 
                   to_date: Optional[str] = None) -> List[Dict]:
        """
        Get stock splits for a ticker. Critical for small caps which often have reverse splits.
        
        Args:
            ticker: Stock ticker symbol
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            
        Returns:
            List of split dictionaries with execution_date and split_ratio
        """
        endpoint = f"/v3/reference/splits"
        params = {'ticker': ticker}
        
        if from_date:
            params['execution_date.gte'] = from_date
        if to_date:
            params['execution_date.lte'] = to_date
        
        try:
            data = self._make_request(endpoint, params)
            return data.get('results', [])
        except Exception as e:
            logger.warning(f"Error fetching splits for {ticker}: {str(e)}")
            return []
    
    def get_dividends(self, ticker: str, from_date: Optional[str] = None,
                     to_date: Optional[str] = None) -> List[Dict]:
        """
        Get dividend information for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            
        Returns:
            List of dividend dictionaries
        """
        endpoint = f"/v3/reference/dividends"
        params = {'ticker': ticker}
        
        if from_date:
            params['ex_dividend_date.gte'] = from_date
        if to_date:
            params['ex_dividend_date.lte'] = to_date
        
        try:
            data = self._make_request(endpoint, params)
            return data.get('results', [])
        except Exception as e:
            logger.warning(f"Error fetching dividends for {ticker}: {str(e)}")
            return []
    
    def get_previous_close(self, ticker: str, adjusted: bool = True) -> Optional[Dict]:
        """
        Get previous trading day's close for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            adjusted: Whether to adjust for splits
            
        Returns:
            Previous close data dictionary or None
        """
        endpoint = f"/v2/aggs/ticker/{ticker}/prev"
        params = {'adjusted': str(adjusted).lower()}
        
        try:
            data = self._make_request(endpoint, params)
            results = data.get('results', [])
            return results[0] if results else None
        except Exception as e:
            logger.warning(f"Error fetching previous close for {ticker}: {str(e)}")
            return None
    
    def get_snapshot(self, ticker: str) -> Optional[Dict]:
        """
        Get current snapshot of ticker (current price, volume, etc).
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Snapshot dictionary or None
        """
        endpoint = f"/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}"
        
        try:
            data = self._make_request(endpoint)
            return data.get('ticker')
        except Exception as e:
            logger.warning(f"Error fetching snapshot for {ticker}: {str(e)}")
            return None
    
    def screen_for_gap_ups(self, date: str, min_gap_percent: float = 10.0,
                          max_market_cap: Optional[float] = None,
                          min_volume: Optional[int] = None) -> List[Dict]:
        """
        Screen for stocks that gapped up on a specific date.
        
        Args:
            date: Date to screen (YYYY-MM-DD)
            min_gap_percent: Minimum gap up percentage
            max_market_cap: Maximum market cap filter (USD)
            min_volume: Minimum volume filter
            
        Returns:
            List of dictionaries containing ticker, gap_percent, volume, market_cap
        """
        # Get all active tickers for that date
        tickers = self.get_all_tickers(active=True, date=date, limit=1000)
        
        gap_ups = []
        
        for ticker_info in tickers:
            ticker = ticker_info.get('ticker')
            if not ticker:
                continue
            
            # Skip non-common stocks
            ticker_type = ticker_info.get('type', '')
            if ticker_type not in ['CS', 'ADRC']:  # Common Stock, ADR Common
                continue
            
            try:
                # Get previous day close and current day open
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                prev_date = date_obj - timedelta(days=1)
                
                # Get up to 5 days of data to ensure we have previous close
                from_date = (date_obj - timedelta(days=5)).strftime('%Y-%m-%d')
                bars = self.get_daily_bars(ticker, from_date, date)
                
                if len(bars) < 2:
                    continue
                
                # Find the current day and previous close
                current_bar = None
                prev_close = None
                
                for i, bar in enumerate(bars):
                    bar_date = datetime.fromtimestamp(bar['t'] / 1000).strftime('%Y-%m-%d')
                    if bar_date == date:
                        current_bar = bar
                        if i > 0:
                            prev_close