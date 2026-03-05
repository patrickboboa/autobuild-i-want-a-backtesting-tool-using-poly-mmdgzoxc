from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum


class ExitType(Enum):
    """Types of exit conditions"""
    PROFIT_TARGET = "profit_target"
    STOP_LOSS = "stop_loss"
    MAX_HOLD_TIME = "max_hold_time"
    END_OF_DAY = "end_of_day"
    FORCED_LIQUIDATION = "forced_liquidation"


class FillModel(Enum):
    """Fill execution models"""
    IMMEDIATE = "immediate"  # Fill at exact price (unrealistic)
    MARKET_OPEN = "market_open"  # Fill at open with slippage
    DELAYED = "delayed"  # Fill after X minutes with slippage
    VWAP = "vwap"  # Fill at VWAP over first X minutes


@dataclass
class EntryParameters:
    """Parameters for identifying gap-up entry opportunities"""
    
    # Gap criteria
    min_gap_percent: float = 20.0  # Minimum gap up percentage from previous close
    max_gap_percent: float = 200.0  # Maximum gap up (avoid extreme outliers)
    
    # Volume criteria
    min_volume_multiplier: float = 2.0  # vs average daily volume
    min_premarket_volume: int = 50000  # Minimum premarket share volume
    
    # Market cap filters (at previous day close)
    min_market_cap: float = 1_000_000  # $1M minimum
    max_market_cap: float = 300_000_000  # $300M maximum (small cap range)
    
    # Price filters
    min_price: float = 1.0  # Avoid sub-dollar stocks (different dynamics)
    max_price: float = 20.0  # Focus on lower-priced small caps
    
    # Liquidity requirements
    min_average_daily_volume: int = 100_000  # shares
    min_average_daily_dollar_volume: float = 500_000  # dollars
    
    # News/catalyst requirements
    require_news_catalyst: bool = False  # Set True if using news data
    
    # Time filters
    min_time_after_open_minutes: int = 0  # Wait X minutes after open before entry
    max_time_after_open_minutes: int = 30  # Don't enter after X minutes
    
    # Entry execution model
    fill_model: FillModel = FillModel.DELAYED
    entry_delay_minutes: int = 5  # Minutes after open before fill
    entry_slippage_percent: float = 0.5  # Additional slippage on entry (%)
    entry_slippage_fixed: float = 0.05  # Fixed slippage per share ($)
    
    # Partial fill modeling
    allow_partial_fills: bool = True
    min_fill_percent: float = 50.0  # Minimum % of order that must fill
    expected_fill_percent: float = 80.0  # Expected fill rate for illiquid stocks


@dataclass
class ExitParameters:
    """Parameters for exit conditions"""
    
    # Profit targets
    profit_target_percent: float = 15.0  # Target profit (negative gap fade)
    profit_target_enabled: bool = True
    
    # Stop loss
    stop_loss_percent: float = 10.0  # Stop loss (gap continues higher)
    stop_loss_enabled: bool = True
    trailing_stop_enabled: bool = False
    trailing_stop_percent: float = 5.0
    
    # Time-based exits
    max_hold_time_minutes: int = 240  # 4 hours max hold
    force_exit_before_close_minutes: int = 15  # Exit X minutes before close
    hold_overnight: bool = False  # Allow overnight positions (risky for shorts)
    
    # Exit execution
    exit_slippage_percent: float = 0.5  # Slippage on exit (%)
    exit_slippage_fixed: float = 0.05  # Fixed slippage per share ($)
    exit_fill_model: FillModel = FillModel.MARKET_OPEN
    
    # Dynamic stop adjustments
    use_atr_stops: bool = False  # Use ATR-based stops instead of fixed %
    atr_multiplier: float = 2.0
    
    # Volatility circuit breaker (halt expansion exits)
    exit_on_trading_halt: bool = True
    exit_on_extreme_volatility: bool = True
    extreme_volatility_threshold: float = 50.0  # % move in 5 minutes


@dataclass
class RiskParameters:
    """Risk management and position sizing"""
    
    # Position sizing
    position_size_method: str = "fixed_dollar"  # fixed_dollar, fixed_shares, kelly, volatility
    fixed_dollar_amount: float = 10_000  # Per position
    fixed_share_amount: int = 1000  # Per position
    max_position_percent: float = 10.0  # % of portfolio
    
    # Portfolio limits
    max_open_positions: int = 5
    max_daily_trades: int = 10
    max_sector_exposure: float = 30.0  # % of portfolio in one sector
    
    # Margin and borrowing
    margin_requirement: float = 50.0  # % margin requirement for shorts
    margin_call_threshold: float = 30.0  # Liquidate if margin drops below this
    margin_cushion: float = 10.0  # Extra margin buffer (%)
    
    # Borrow costs (critical for small cap shorts)
    hard_to_borrow_cost_annual: float = 50.0  # % annual cost to borrow
    borrow_cost_calculation: str = "daily"  # daily, per_position
    assume_shares_available: float = 80.0  # % of time shares available to borrow
    borrow_unavailable_action: str = "skip"  # skip, queue, reduce_size
    
    # Risk limits
    max_loss_per_trade: float = 2.0  # % of portfolio
    max_daily_loss: float = 5.0  # % of portfolio
    max_drawdown_pause: float = 15.0  # Stop trading if drawdown exceeds this %
    
    # Concentration limits
    max_correlation_overlap: float = 0.7  # Don't add position if correlation > this
    check_correlation: bool = False


@dataclass
class CostParameters:
    """Transaction costs and fees"""
    
    # Commission structure
    commission_per_share: float = 0.005
    commission_minimum: float = 1.0
    commission_maximum: float = 5.0
    
    # SEC fees (shorts only on sales, which is covering)
    sec_fee_per_dollar: float = 0.0000278  # 2024 rate
    
    # Borrow fees (already in RiskParameters but repeated for clarity)
    short_borrow_rate_annual: float = 50.0  # Hard to borrow rate
    
    # Slippage (already in Entry/Exit but aggregate here)
    use_bid_ask_spread: bool = True
    assumed_spread_percent: float = 1.0  # % spread for illiquid small caps
    
    # Other costs
    platform_fees: float = 0.0  # Monthly platform fees allocated per trade
    data_feed_costs: float = 0.0  # Allocated per trade


@dataclass
class DataParameters:
    """Data handling and quality parameters"""
    
    # Data source settings
    use_adjusted_prices: bool = True  # Adjust for splits
    handle_delisted_stocks: bool = True  # Include delisted for survivorship bias
    
    # Corporate actions
    adjust_for_splits: bool = True
    adjust_for_reverse_splits: bool = True
    min_split_ratio: float = 0.1  # Ignore tiny adjustments
    
    # Data quality filters
    min_data_points_required: int = 20  # Minimum bars needed for entry
    exclude_low_quality_data: bool = True
    require_complete_day_data: bool = True
    
    # Look-ahead bias prevention
    use_point_in_time_data: bool = True  # Critical: only use data available at decision time
    calculate_market_cap_at_entry: bool = True  # Don't use EOD market cap
    
    # Timestamp handling
    bar_interval_minutes: int = 1  # Use 1-minute bars for precision
    premarket_start_time: str = "04:00"  # Eastern time
    market_open_time: str = "09:30"
    market_close_time: str = "16:00"
    
    # Caching
    cache_historical_data: bool = True
    cache_ttl_hours: int = 24


@dataclass
class BacktestParameters:
    """Backtesting-specific parameters"""
    
    # Test period
    start_date: str = "2020-01-01"
    end_date: str = "2024-12-31"
    
    # Validation approach
    use_walk_forward: bool = True
    walk_forward_train_days: int = 252  # 1 year training
    walk_forward_test_days: int = 63  # Quarter testing
    walk_forward_step_days: int = 21  # Monthly steps
    
    # Optimization
    optimize_parameters: bool = False
    optimization_metric: str = "sharpe_ratio"  # sharpe_ratio, total_return, win_rate
    max_parameter_combinations: int = 100
    
    # Monte Carlo
    run_monte_carlo: bool = False
    monte_carlo_simulations: int = 1000
    
    # Benchmark
    benchmark_symbol: str = "SPY"
    compare_to_benchmark: bool = True
    
    # Initial conditions
    initial_capital: float = 100_000
    reinvest_profits: bool = True
    
    # Reporting
    generate_detailed_logs: bool = True
    save_trade_history: bool = True
    save_equity_curve: bool = True


@dataclass
class Strategy:
    """Complete strategy configuration"""
    
    name: str = "SmallCap Gap Fade Short Strategy"
    version: str = "1.0.0"
    description: str = "Short small caps that gap up significantly, betting on mean reversion"
    
    # Strategy components
    entry: EntryParameters = field(default_factory=EntryParameters)
    exit: ExitParameters = field(default_factory=ExitParameters)
    risk: RiskParameters = field(default_factory=RiskParameters)
    costs: CostParameters = field(default_factory=CostParameters)
    data: DataParameters = field(default_factory=DataParameters)
    backtest: BacktestParameters = field(default_factory=BacktestParameters)
    
    # Strategy state
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert strategy to dictionary"""
        return {
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'entry': self.entry.__dict__,
            'exit': self.exit.__dict__,
            'risk': self.risk.__dict__,
            'costs': self.costs.__dict__,
            'data': self.data.__dict__,
            'backtest': self.backtest.__dict__,
            'enabled': self.enabled
        }
    
    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> 'Strategy':
        """Create strategy from dictionary"""
        strategy = cls(
            name=config.get('name', 'SmallCap Gap Fade Short Strategy'),
            version=config.get('version', '1.0.0'),
            description=config.get('description', ''),
            enabled=config.get('enabled', True)
        )
        
        if 'entry' in config:
            strategy.entry = EntryParameters(**config['entry'])
        if 'exit' in config:
            strategy.exit = ExitParameters(**config['exit'])
        if 'risk' in config:
            strategy.risk = RiskParameters(**config['risk'])
        if 'costs' in config:
            strategy.costs = CostParameters(**config['costs'])
        if 'data' in config:
            strategy.data = DataParameters(**config['data'])
        if 'backtest' in config:
            strategy.backtest = BacktestParameters(**config['backtest'])
        
        return strategy
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate strategy parameters"""
        
        # Entry validations
        if self.entry.min_gap_percent >= self.entry.max_gap_percent:
            return False, "min_gap_percent must be less than max_gap_percent"
        
        if self.entry.min_market_cap >= self.entry.max_market_cap:
            return False, "min_market_cap must be less than max_market_cap"
        
        if self.entry.min_price >= self.entry.max_price:
            return False, "min_price must be less than max_price"
        
        # Exit validations
        if self.exit.profit_target_percent <= 0:
            return False, "profit_target_percent must be positive"
        
        if self.exit.stop_loss_percent <= 0:
            return False, "stop_loss_percent must be positive"
        
        if self.exit.max_hold_time_minutes <= 0:
            return False, "max_hold_time_minutes must be positive"
        
        # Risk validations
        if self.risk.margin_requirement < 25.0 or self.risk.margin_requirement > 100.0:
            return False, "margin_requirement must be between 25 and 100"
        
        if self.risk.max_position_percent <= 0 or self.risk.max_position_percent > 100:
            return False, "max_position_percent must be between 0 and 100"
        
        if self.risk.max_open_positions <= 0:
            return False, "max_open_positions must be positive"
        
        # Cost validations
        if self.costs.commission_per_share < 0:
            return False, "commission_per_share cannot be negative"
        
        # Data validations
        if self.data.bar_interval_minutes <= 0:
            return False, "bar_interval_minutes must be positive"
        
        # Backtest validations
        if self.backtest.initial_capital <= 0:
            return False, "initial_capital must be positive"
        
        return True, None
    
    def calculate_borrow_cost_per_day(self, position_value: float) -> float:
        """Calculate daily borrow cost for a short position"""
        annual_cost = position_value * (self.risk.hard_to_borrow_cost_annual / 100.0)
        daily_cost = annual_cost / 365.0
        return daily_cost
    
    def calculate_total_entry_cost(self, shares: int, entry_price: float) -> float:
        """Calculate total cost to enter position including slippage and commissions"""
        position_value = shares * entry_price
        
        # Commission
        commission = max(
            self.costs.commission_minimum,
            min(self.costs.commission_maximum, shares * self.costs.commission_per_share)
        )
        
        # Slippage (for shorts, slippage increases entry cost)
        slippage_percent_cost = position_value * (self.entry.entry_slippage_percent / 100.0)
        slippage_fixed_cost = shares * self.entry.entry_slippage_fixed
        
        # Bid-ask spread
        spread_cost = 0.0
        if self.costs.use_bid_ask_spread:
            spread_cost = position_value * (self.costs.assumed_spread_percent /