import os
from datetime import datetime, timedelta
from typing import Dict, Any
import logging
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuration management for the backtesting tool"""
    
    # API Configuration
    POLYGON_API_KEY = os.getenv('POLYGON_API_KEY', '')
    POLYGON_BASE_URL = 'https://api.polygon.io'
    
    # Date Range Configuration
    DEFAULT_START_DATE = (datetime.now() - timedelta(days=365*3)).strftime('%Y-%m-%d')
    DEFAULT_END_DATE = datetime.now().strftime('%Y-%m-%d')
    WALK_FORWARD_TRAIN_DAYS = 365
    WALK_FORWARD_TEST_DAYS = 90
    ENABLE_WALK_FORWARD = True
    
    # Data Configuration
    USE_MINUTE_BARS = True
    MINUTE_BAR_TIMESPAN = 1
    AGGREGATE_TIMESPAN = 'minute'
    INCLUDE_DELISTED = True
    PRE_MARKET_START = '04:00'
    MARKET_OPEN = '09:30'
    MARKET_CLOSE = '16:00'
    AFTER_HOURS_END = '20:00'
    
    # Screener Configuration - Gap Up Detection
    MIN_GAP_PERCENT = 10.0
    MAX_GAP_PERCENT = 200.0
    MIN_PREVIOUS_CLOSE_PRICE = 0.50
    MAX_PREVIOUS_CLOSE_PRICE = 20.0
    MIN_PREVIOUS_DAY_VOLUME = 50000
    MIN_RELATIVE_VOLUME = 1.5
    
    # Market Cap Filters (calculated at entry time to avoid look-ahead bias)
    MIN_MARKET_CAP = 1_000_000
    MAX_MARKET_CAP = 500_000_000
    MARKET_CAP_CALCULATION_METHOD = 'entry_time'
    
    # Strategy Parameters - Entry
    ENTRY_DELAY_MINUTES = 5
    ENTRY_TIMEFRAME_START = '09:30'
    ENTRY_TIMEFRAME_END = '10:30'
    USE_LIMIT_ORDERS = True
    ENTRY_LIMIT_OFFSET_PERCENT = 0.5
    MAX_ENTRY_ATTEMPTS = 3
    PARTIAL_FILL_THRESHOLD = 0.5
    
    # Strategy Parameters - Exit
    PROFIT_TARGET_PERCENT = 15.0
    STOP_LOSS_PERCENT = 8.0
    TRAILING_STOP_ENABLED = True
    TRAILING_STOP_ACTIVATION_PERCENT = 5.0
    TRAILING_STOP_DISTANCE_PERCENT = 3.0
    MAX_HOLD_DAYS = 5
    EXIT_AT_CLOSE = False
    END_OF_DAY_EXIT_TIME = '15:45'
    
    # Risk Management - Position Sizing
    INITIAL_CAPITAL = 100000.0
    MAX_POSITION_SIZE_PERCENT = 10.0
    MAX_POSITIONS = 5
    POSITION_SIZING_METHOD = 'equal_weight'
    RISK_PER_TRADE_PERCENT = 2.0
    
    # Risk Management - Margin and Liquidation
    MARGIN_REQUIREMENT = 0.5
    MAINTENANCE_MARGIN = 0.25
    ENABLE_MARGIN_CALLS = True
    FORCED_LIQUIDATION_THRESHOLD = 0.30
    MARGIN_CALL_BUFFER = 0.05
    
    # Short Selling Costs and Constraints
    DEFAULT_BORROW_RATE_ANNUAL = 0.15
    HARD_TO_BORROW_RATE_ANNUAL = 0.50
    EXTREME_HTB_RATE_ANNUAL = 1.50
    BORROW_RATE_CALCULATION_METHOD = 'tiered'
    
    # Tiered borrow rates based on price and liquidity
    BORROW_RATE_TIERS = {
        'low_risk': {'max_price': 10, 'min_volume': 500000, 'rate': 0.10},
        'medium_risk': {'max_price': 5, 'min_volume': 100000, 'rate': 0.35},
        'high_risk': {'max_price': 2, 'min_volume': 50000, 'rate': 0.80},
        'extreme_risk': {'rate': 1.50}
    }
    
    # Stock availability for shorting (probability model)
    STOCK_AVAILABILITY_THRESHOLD = 0.80
    HTB_AVAILABILITY_PENALTY_FACTOR = 0.50
    MINIMUM_LOCATE_FEE = 0.01
    
    # Execution Realism - Slippage and Fills
    ENABLE_SLIPPAGE = True
    BASE_SLIPPAGE_PERCENT = 0.10
    VOLUME_SLIPPAGE_FACTOR = 0.05
    SPREAD_SLIPPAGE_MULTIPLIER = 0.5
    
    # Bid-Ask Spread Modeling
    ENABLE_SPREAD_MODELING = True
    MIN_SPREAD_PERCENT = 0.05
    TYPICAL_SPREAD_PERCENT = 0.25
    ILLIQUID_SPREAD_PERCENT = 1.0
    SPREAD_CALCULATION_METHOD = 'volume_based'
    
    # Execution Fill Modeling
    INSTANT_FILL_PROBABILITY = 0.30
    PARTIAL_FILL_PROBABILITY = 0.50
    NO_FILL_PROBABILITY = 0.20
    AVERAGE_FILL_PERCENTAGE = 0.70
    GAP_STOCK_FILL_REDUCTION = 0.30
    
    # Overnight Gap Risk
    OVERNIGHT_POSITION_RISK_MULTIPLIER = 1.5
    TRACK_OVERNIGHT_GAPS = True
    MAX_OVERNIGHT_GAP_TOLERANCE_PERCENT = 20.0
    
    # Corporate Actions
    ADJUST_FOR_SPLITS = True
    ADJUST_FOR_REVERSE_SPLITS = True
    HANDLE_DELISTINGS = True
    DELISTING_LOSS_PERCENT = 100.0
    SPLIT_ANNOUNCEMENT_DAYS = 10
    
    # Transaction Costs
    COMMISSION_PER_TRADE = 0.0
    SEC_FEE_RATE = 0.0000278
    FINRA_TAF = 0.000166
    ENABLE_REGULATORY_FEES = True
    
    # Data Caching
    ENABLE_CACHING = True
    CACHE_DIRECTORY = 'cache'
    CACHE_EXPIRY_DAYS = 7
    CACHE_MINUTE_BARS = True
    CACHE_DAILY_BARS = True
    CACHE_TICKER_DETAILS = True
    
    # Logging Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_FILE = 'backtest.log'
    ENABLE_FILE_LOGGING = True
    ENABLE_CONSOLE_LOGGING = True
    LOG_TRADES = True
    LOG_FILLS = True
    LOG_MARGIN_EVENTS = True
    
    # Analytics Configuration
    CALCULATE_SHARPE_RATIO = True
    CALCULATE_SORTINO_RATIO = True
    CALCULATE_MAX_DRAWDOWN = True
    CALCULATE_WIN_RATE = True
    RISK_FREE_RATE = 0.04
    TRADING_DAYS_PER_YEAR = 252
    
    # Visualization Settings
    PLOT_EQUITY_CURVE = True
    PLOT_DRAWDOWN = True
    PLOT_RETURNS_DISTRIBUTION = True
    PLOT_ROLLING_METRICS = True
    SAVE_PLOTS = True
    PLOT_DIRECTORY = 'plots'
    PLOT_DPI = 300
    
    # Validation and Optimization
    MIN_TRADES_FOR_VALIDATION = 30
    MAX_PARAMETER_COMBINATIONS = 100
    ENABLE_MONTE_CARLO = True
    MONTE_CARLO_SIMULATIONS = 1000
    ENABLE_SENSITIVITY_ANALYSIS = True
    
    # Performance Tracking
    TRACK_PER_STOCK_PERFORMANCE = True
    TRACK_PER_DAY_PERFORMANCE = True
    TRACK_SECTOR_PERFORMANCE = True
    TRACK_MARKET_CAP_BUCKETS = True
    
    # Alert Thresholds
    MAX_DAILY_LOSS_PERCENT = 5.0
    MAX_TOTAL_DRAWDOWN_PERCENT = 20.0
    MIN_WIN_RATE_THRESHOLD = 0.40
    
    # Advanced Strategy Parameters
    ENABLE_VOLUME_PROFILE_FILTER = True
    MIN_FLOAT_SHARES = 1_000_000
    MAX_FLOAT_SHARES = 50_000_000
    EXCLUDE_RECENT_IPOS_DAYS = 90
    REQUIRE_NEWS_CATALYST = False
    
    # Backtesting Engine Settings
    ENABLE_PARALLEL_PROCESSING = False
    MAX_WORKERS = 4
    BATCH_SIZE = 100
    PROGRESS_UPDATE_FREQUENCY = 10
    
    @classmethod
    def validate(cls) -> bool:
        """Validate configuration settings"""
        if not cls.POLYGON_API_KEY:
            raise ValueError("POLYGON_API_KEY not set in environment variables")
        
        if cls.MIN_GAP_PERCENT >= cls.MAX_GAP_PERCENT:
            raise ValueError("MIN_GAP_PERCENT must be less than MAX_GAP_PERCENT")
        
        if cls.MIN_MARKET_CAP >= cls.MAX_MARKET_CAP:
            raise ValueError("MIN_MARKET_CAP must be less than MAX_MARKET_CAP")
        
        if cls.INITIAL_CAPITAL <= 0:
            raise ValueError("INITIAL_CAPITAL must be positive")
        
        if cls.MAX_POSITION_SIZE_PERCENT > 100 or cls.MAX_POSITION_SIZE_PERCENT <= 0:
            raise ValueError("MAX_POSITION_SIZE_PERCENT must be between 0 and 100")
        
        if cls.MARGIN_REQUIREMENT < cls.MAINTENANCE_MARGIN:
            raise ValueError("MARGIN_REQUIREMENT must be >= MAINTENANCE_MARGIN")
        
        return True
    
    @classmethod
    def get_strategy_params(cls) -> Dict[str, Any]:
        """Get all strategy-related parameters"""
        return {
            'min_gap_percent': cls.MIN_GAP_PERCENT,
            'max_gap_percent': cls.MAX_GAP_PERCENT,
            'min_previous_close_price': cls.MIN_PREVIOUS_CLOSE_PRICE,
            'max_previous_close_price': cls.MAX_PREVIOUS_CLOSE_PRICE,
            'min_market_cap': cls.MIN_MARKET_CAP,
            'max_market_cap': cls.MAX_MARKET_CAP,
            'profit_target_percent': cls.PROFIT_TARGET_PERCENT,
            'stop_loss_percent': cls.STOP_LOSS_PERCENT,
            'trailing_stop_enabled': cls.TRAILING_STOP_ENABLED,
            'trailing_stop_activation_percent': cls.TRAILING_STOP_ACTIVATION_PERCENT,
            'trailing_stop_distance_percent': cls.TRAILING_STOP_DISTANCE_PERCENT,
            'max_hold_days': cls.MAX_HOLD_DAYS,
            'entry_delay_minutes': cls.ENTRY_DELAY_MINUTES
        }
    
    @classmethod
    def get_risk_params(cls) -> Dict[str, Any]:
        """Get all risk management parameters"""
        return {
            'initial_capital': cls.INITIAL_CAPITAL,
            'max_position_size_percent': cls.MAX_POSITION_SIZE_PERCENT,
            'max_positions': cls.MAX_POSITIONS,
            'risk_per_trade_percent': cls.RISK_PER_TRADE_PERCENT,
            'margin_requirement': cls.MARGIN_REQUIREMENT,
            'maintenance_margin': cls.MAINTENANCE_MARGIN,
            'default_borrow_rate': cls.DEFAULT_BORROW_RATE_ANNUAL,
            'enable_margin_calls': cls.ENABLE_MARGIN_CALLS
        }
    
    @classmethod
    def setup_logging(cls):
        """Setup logging configuration"""
        handlers = []
        
        if cls.ENABLE_FILE_LOGGING:
            file_handler = logging.FileHandler(cls.LOG_FILE)
            file_handler.setFormatter(logging.Formatter(cls.LOG_FORMAT))
            handlers.append(file_handler)
        
        if cls.ENABLE_CONSOLE_LOGGING:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter(cls.LOG_FORMAT))
            handlers.append(console_handler)
        
        logging.basicConfig(
            level=getattr(logging, cls.LOG_LEVEL.upper()),
            format=cls.LOG_FORMAT,
            handlers=handlers
        )
        
        return logging.getLogger(__name__)