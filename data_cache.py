import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
import threading
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class DataCache:
    """SQLite-based caching layer for historical market data from Polygon API."""
    
    def __init__(self, db_path: str = "data/market_cache.db"):
        """Initialize the data cache.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._local = threading.local()
        
        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database schema
        self._init_db()
        
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    @contextmanager
    def _get_cursor(self):
        """Context manager for database cursor."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            cursor.close()
    
    def _init_db(self):
        """Initialize database schema."""
        with self._get_cursor() as cursor:
            # Minute bars table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS minute_bars (
                    ticker TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume INTEGER NOT NULL,
                    vwap REAL,
                    transactions INTEGER,
                    PRIMARY KEY (ticker, timestamp)
                )
            """)
            
            # Daily bars table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_bars (
                    ticker TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume INTEGER NOT NULL,
                    vwap REAL,
                    transactions INTEGER,
                    PRIMARY KEY (ticker, date)
                )
            """)
            
            # Ticker details/snapshots table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ticker_details (
                    ticker TEXT NOT NULL,
                    date TEXT NOT NULL,
                    name TEXT,
                    market_cap REAL,
                    shares_outstanding REAL,
                    sector TEXT,
                    industry TEXT,
                    exchange TEXT,
                    is_active BOOLEAN,
                    details_json TEXT,
                    PRIMARY KEY (ticker, date)
                )
            """)
            
            # Corporate actions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS corporate_actions (
                    ticker TEXT NOT NULL,
                    ex_date TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    ratio REAL,
                    details_json TEXT,
                    PRIMARY KEY (ticker, ex_date, action_type)
                )
            """)
            
            # Ticker universe/listing history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ticker_universe (
                    ticker TEXT PRIMARY KEY,
                    name TEXT,
                    first_seen TEXT,
                    last_seen TEXT,
                    is_delisted BOOLEAN DEFAULT 0,
                    delisting_date TEXT,
                    exchange TEXT,
                    asset_type TEXT,
                    metadata_json TEXT
                )
            """)
            
            # Cache metadata for tracking freshness
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_metadata (
                    cache_key TEXT PRIMARY KEY,
                    last_updated INTEGER NOT NULL,
                    expires_at INTEGER,
                    data_json TEXT
                )
            """)
            
            # Create indexes for better query performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_minute_bars_ticker_time 
                ON minute_bars(ticker, timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_daily_bars_ticker_date 
                ON daily_bars(ticker, date)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ticker_details_date 
                ON ticker_details(date, ticker)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_corporate_actions_date 
                ON corporate_actions(ex_date, ticker)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ticker_universe_active 
                ON ticker_universe(is_delisted, last_seen)
            """)
    
    def cache_minute_bars(self, ticker: str, bars: List[Dict[str, Any]]):
        """Cache minute bar data.
        
        Args:
            ticker: Stock ticker symbol
            bars: List of bar dictionaries with OHLCV data
        """
        if not bars:
            return
            
        with self._get_cursor() as cursor:
            cursor.executemany("""
                INSERT OR REPLACE INTO minute_bars 
                (ticker, timestamp, open, high, low, close, volume, vwap, transactions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                (
                    ticker.upper(),
                    bar['t'],
                    bar['o'],
                    bar['h'],
                    bar['l'],
                    bar['c'],
                    bar['v'],
                    bar.get('vw'),
                    bar.get('n')
                )
                for bar in bars
            ])
        
        logger.debug(f"Cached {len(bars)} minute bars for {ticker}")
    
    def get_minute_bars(
        self,
        ticker: str,
        start_timestamp: int,
        end_timestamp: int
    ) -> List[Dict[str, Any]]:
        """Retrieve cached minute bars.
        
        Args:
            ticker: Stock ticker symbol
            start_timestamp: Start timestamp (milliseconds)
            end_timestamp: End timestamp (milliseconds)
            
        Returns:
            List of bar dictionaries
        """
        with self._get_cursor() as cursor:
            cursor.execute("""
                SELECT timestamp as t, open as o, high as h, low as l, 
                       close as c, volume as v, vwap as vw, transactions as n
                FROM minute_bars
                WHERE ticker = ? AND timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp
            """, (ticker.upper(), start_timestamp, end_timestamp))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def cache_daily_bars(self, ticker: str, bars: List[Dict[str, Any]]):
        """Cache daily bar data.
        
        Args:
            ticker: Stock ticker symbol
            bars: List of bar dictionaries with OHLCV data
        """
        if not bars:
            return
            
        with self._get_cursor() as cursor:
            cursor.executemany("""
                INSERT OR REPLACE INTO daily_bars 
                (ticker, date, open, high, low, close, volume, vwap, transactions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                (
                    ticker.upper(),
                    bar['date'],
                    bar['o'],
                    bar['h'],
                    bar['l'],
                    bar['c'],
                    bar['v'],
                    bar.get('vw'),
                    bar.get('n')
                )
                for bar in bars
            ])
        
        logger.debug(f"Cached {len(bars)} daily bars for {ticker}")
    
    def get_daily_bars(
        self,
        ticker: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """Retrieve cached daily bars.
        
        Args:
            ticker: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            List of bar dictionaries
        """
        with self._get_cursor() as cursor:
            cursor.execute("""
                SELECT date, open as o, high as h, low as l, 
                       close as c, volume as v, vwap as vw, transactions as n
                FROM daily_bars
                WHERE ticker = ? AND date >= ? AND date <= ?
                ORDER BY date
            """, (ticker.upper(), start_date, end_date))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def cache_ticker_details(
        self,
        ticker: str,
        date: str,
        details: Dict[str, Any]
    ):
        """Cache ticker details for a specific date.
        
        Args:
            ticker: Stock ticker symbol
            date: Date for the details (YYYY-MM-DD)
            details: Dictionary with ticker details
        """
        with self._get_cursor() as cursor:
            cursor.execute("""
                INSERT OR REPLACE INTO ticker_details 
                (ticker, date, name, market_cap, shares_outstanding, 
                 sector, industry, exchange, is_active, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker.upper(),
                date,
                details.get('name'),
                details.get('market_cap'),
                details.get('shares_outstanding') or details.get('weighted_shares_outstanding'),
                details.get('sector') or details.get('sic_description'),
                details.get('industry'),
                details.get('primary_exchange') or details.get('exchange'),
                details.get('active', True),
                json.dumps(details)
            ))
    
    def get_ticker_details(
        self,
        ticker: str,
        date: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve ticker details for a specific date.
        
        Args:
            ticker: Stock ticker symbol
            date: Date for the details (YYYY-MM-DD)
            
        Returns:
            Dictionary with ticker details or None
        """
        with self._get_cursor() as cursor:
            # Try exact date first
            cursor.execute("""
                SELECT details_json FROM ticker_details
                WHERE ticker = ? AND date = ?
            """, (ticker.upper(), date))
            
            row = cursor.fetchone()
            if row and row['details_json']:
                return json.loads(row['details_json'])
            
            # Fall back to most recent details before the date
            cursor.execute("""
                SELECT details_json FROM ticker_details
                WHERE ticker = ? AND date <= ?
                ORDER BY date DESC
                LIMIT 1
            """, (ticker.upper(), date))
            
            row = cursor.fetchone()
            if row and row['details_json']:
                return json.loads(row['details_json'])
            
            return None
    
    def cache_corporate_action(
        self,
        ticker: str,
        ex_date: str,
        action_type: str,
        ratio: Optional[float],
        details: Dict[str, Any]
    ):
        """Cache corporate action (split, reverse split, etc.).
        
        Args:
            ticker: Stock ticker symbol
            ex_date: Ex-date of the action (YYYY-MM-DD)
            action_type: Type of action (split, reverse_split, etc.)
            ratio: Split ratio (e.g., 2.0 for 2:1 split)
            details: Full details dictionary
        """
        with self._get_cursor() as cursor:
            cursor.execute("""
                INSERT OR REPLACE INTO corporate_actions 
                (ticker, ex_date, action_type, ratio, details_json)
                VALUES (?, ?, ?, ?, ?)
            """, (
                ticker.upper(),
                ex_date,
                action_type,
                ratio,
                json.dumps(details)
            ))
    
    def get_corporate_actions(
        self,
        ticker: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """Retrieve corporate actions for a date range.
        
        Args:
            ticker: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            List of corporate action dictionaries
        """
        with self._get_cursor() as cursor:
            cursor.execute("""
                SELECT ex_date, action_type, ratio, details_json
                FROM corporate_actions
                WHERE ticker = ? AND ex_date >= ? AND ex_date <= ?
                ORDER BY ex_date
            """, (ticker.upper(), start_date, end_date))
            
            rows = cursor.fetchall()
            actions = []
            for row in rows:
                action = json.loads(row['details_json'])
                action['ex_date'] = row['ex_date']
                action['action_type'] = row['action_type']
                action['ratio'] = row['ratio']
                actions.append(action)
            
            return actions
    
    def update_ticker_universe(
        self,
        ticker: str,
        name: Optional[str] = None,
        first_seen: Optional[str] = None,
        last_seen: Optional[str] = None,
        is_delisted: bool = False,
        delisting_date: Optional[str] = None,
        exchange: Optional[str] = None,
        asset_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Update ticker universe with listing/delisting information.
        
        Args:
            ticker: Stock ticker symbol
            name: Company name
            first_seen: First date ticker was observed
            last_seen: Last date ticker was observed
            is_delisted: Whether ticker is delisted
            delisting_date: Date of delisting
            exchange: Primary exchange
            asset_type: Asset type (CS, ETF, etc.)
            metadata: Additional metadata
        """
        with self._get_cursor() as cursor:
            # Check if ticker exists
            cursor.execute("""
                SELECT ticker, first_seen, last_seen FROM ticker_universe
                WHERE ticker = ?
            """, (ticker.upper(),))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing record
                updates = []
                params = []
                
                if name is not None:
                    updates.append("name = ?")
                    params.append(name)
                
                if first_seen and (not existing['first_seen'] or first_seen < existing['first_seen']):
                    updates.append("first_seen = ?")
                    params.append(first_seen)
                
                if last_seen and (not existing['last_seen'] or last_seen > existing['last_seen']):
                    updates.append("last_seen = ?")
                    params.append(last_seen)
                
                if is_delisted:
                    updates.append("is_delisted = ?")
                    params.append(1)
                    
                if delisting_date:
                    updates.append("delisting_date = ?")
                    params.append(delisting_date)
                
                if exchange:
                    updates.append("exchange = ?")
                    params.append(