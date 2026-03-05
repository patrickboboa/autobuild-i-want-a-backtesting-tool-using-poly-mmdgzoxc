import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for backtesting parameters"""
    initial_capital: float = 100000.0
    position_size_pct: float = 0.10  # 10% of portfolio per position
    max_positions: int = 5
    borrow_cost_annual: float = 0.15  # 15% annual hard-to-borrow fee
    commission_per_share: float = 0.005
    min_commission: float = 1.0
    slippage_pct: float = 0.005  # 0.5% slippage on entry/exit
    margin_requirement: float = 1.5  # 150% margin for shorts
    forced_liquidation_threshold: float = 1.3  # Liquidate if margin drops to 130%
    max_holding_days: int = 5
    profit_target_pct: float = 0.20  # 20% profit target
    stop_loss_pct: float = 0.15  # 15% stop loss
    partial_fill_probability: float = 0.3  # 30% chance of partial fill
    partial_fill_amount: float = 0.5  # Fill 50% on partial fills
    execution_delay_minutes: int = 5  # 5 minute delay from signal to fill
    use_limit_orders: bool = True
    limit_order_offset_pct: float = 0.01  # 1% below ask for short entries


@dataclass
class Trade:
    """Represents a single trade"""
    ticker: str
    entry_date: datetime
    entry_price: float
    shares: int
    initial_margin: float
    borrow_cost_daily: float
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    commission_entry: float = 0.0
    commission_exit: float = 0.0
    slippage_entry: float = 0.0
    slippage_exit: float = 0.0
    total_borrow_cost: float = 0.0
    pnl: Optional[float] = None
    return_pct: Optional[float] = None
    days_held: int = 0
    was_partial_fill: bool = False
    was_liquidated: bool = False
    splits_adjusted: List[Tuple[datetime, float]] = field(default_factory=list)


@dataclass
class PositionState:
    """Current state of an open position"""
    trade: Trade
    current_price: float
    current_value: float
    unrealized_pnl: float
    margin_level: float
    days_held: int


class Backtester:
    """Core backtesting engine for short gap-up strategy"""
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.capital = config.initial_capital
        self.initial_capital = config.initial_capital
        self.open_positions: Dict[str, Trade] = {}
        self.closed_trades: List[Trade] = []
        self.equity_curve: List[Tuple[datetime, float]] = []
        self.daily_returns: List[float] = []
        self.cash_available = config.initial_capital
        
    def reset(self):
        """Reset backtester state"""
        self.capital = self.initial_capital
        self.cash_available = self.initial_capital
        self.open_positions = {}
        self.closed_trades = []
        self.equity_curve = []
        self.daily_returns = []
        
    def calculate_position_size(self, price: float) -> int:
        """Calculate number of shares to short based on portfolio size"""
        position_value = self.capital * self.config.position_size_pct
        shares = int(position_value / price)
        
        # Check if we have enough margin
        required_margin = shares * price * self.config.margin_requirement
        if required_margin > self.cash_available:
            shares = int(self.cash_available / (price * self.config.margin_requirement))
            
        return max(shares, 0)
    
    def calculate_commission(self, shares: int, price: float) -> float:
        """Calculate commission costs"""
        commission = shares * self.config.commission_per_share
        return max(commission, self.config.min_commission)
    
    def calculate_slippage(self, shares: int, price: float, is_entry: bool) -> Tuple[float, float]:
        """
        Calculate slippage cost and adjusted price
        Entry (short): we sell at worse price (lower)
        Exit (cover): we buy at worse price (higher)
        """
        slippage_pct = self.config.slippage_pct
        
        if is_entry:
            # Shorting - we sell, so slippage is negative (lower price)
            adjusted_price = price * (1 - slippage_pct)
            slippage_cost = shares * price * slippage_pct
        else:
            # Covering - we buy, so slippage is positive (higher price)
            adjusted_price = price * (1 + slippage_pct)
            slippage_cost = shares * price * slippage_pct
            
        return adjusted_price, slippage_cost
    
    def simulate_partial_fill(self, shares: int) -> Tuple[int, bool]:
        """Simulate partial fill probability"""
        if np.random.random() < self.config.partial_fill_probability:
            filled_shares = int(shares * self.config.partial_fill_amount)
            return max(filled_shares, 1), True
        return shares, False
    
    def apply_execution_delay(self, signal_time: datetime, bars_data: List[Dict]) -> Optional[Dict]:
        """
        Apply execution delay and find the appropriate bar for execution
        Returns the bar at which execution occurs, or None if no valid bar
        """
        execution_time = signal_time + timedelta(minutes=self.config.execution_delay_minutes)
        
        for bar in bars_data:
            bar_time = bar['timestamp']
            if bar_time >= execution_time:
                return bar
                
        return None
    
    def adjust_for_split(self, trade: Trade, split_date: datetime, split_ratio: float):
        """
        Adjust trade for stock split
        split_ratio > 1.0 means forward split (e.g., 2.0 for 2-for-1)
        split_ratio < 1.0 means reverse split (e.g., 0.5 for 1-for-2)
        """
        trade.shares = int(trade.shares * split_ratio)
        trade.entry_price = trade.entry_price / split_ratio
        trade.splits_adjusted.append((split_date, split_ratio))
        logger.info(f"Adjusted {trade.ticker} for split: ratio={split_ratio}, new shares={trade.shares}, new price={trade.entry_price}")
    
    def check_margin_call(self, position: Trade, current_price: float) -> bool:
        """Check if position should be force-liquidated due to margin call"""
        position_value = position.shares * current_price
        initial_short_proceeds = position.shares * position.entry_price
        
        # Calculate current margin level
        # For short: (cash + short_proceeds - current_value) / current_value
        equity = initial_short_proceeds - position_value + position.initial_margin
        margin_level = equity / position_value if position_value > 0 else 0
        
        return margin_level < self.config.forced_liquidation_threshold
    
    def calculate_borrow_cost(self, shares: int, price: float, days_held: int) -> float:
        """Calculate hard-to-borrow cost"""
        position_value = shares * price
        daily_rate = self.config.borrow_cost_annual / 365.0
        return position_value * daily_rate * days_held
    
    def enter_position(
        self, 
        ticker: str, 
        signal_date: datetime,
        entry_bar: Dict,
        gap_pct: float,
        intraday_bars: List[Dict],
        splits_data: Optional[List[Dict]] = None
    ) -> Optional[Trade]:
        """
        Enter a short position
        
        Args:
            ticker: Stock ticker
            signal_date: Date of gap signal
            entry_bar: Bar data for entry (after execution delay)
            gap_pct: Gap percentage (for logging)
            intraday_bars: Minute bars for the day
            splits_data: List of split events to check
        """
        # Check if we already have a position or hit max positions
        if ticker in self.open_positions:
            return None
        if len(self.open_positions) >= self.config.max_positions:
            return None
        
        # Get entry price (ask price, or high of bar as proxy)
        base_price = entry_bar.get('high', entry_bar.get('close'))
        
        # Calculate position size
        shares = self.calculate_position_size(base_price)
        if shares == 0:
            logger.warning(f"Cannot enter {ticker}: insufficient capital for position")
            return None
        
        # Simulate partial fill
        shares, was_partial = self.simulate_partial_fill(shares)
        
        # Apply slippage (entry - we're shorting/selling)
        entry_price, slippage_cost = self.calculate_slippage(shares, base_price, is_entry=True)
        
        # Calculate commission
        commission = self.calculate_commission(shares, entry_price)
        
        # Calculate required margin
        position_value = shares * entry_price
        required_margin = position_value * self.config.margin_requirement
        
        # Check if we have enough cash
        total_cost = required_margin + commission + slippage_cost
        if total_cost > self.cash_available:
            logger.warning(f"Cannot enter {ticker}: insufficient margin (need {total_cost:.2f}, have {self.cash_available:.2f})")
            return None
        
        # Calculate daily borrow cost
        daily_borrow_cost = (position_value * self.config.borrow_cost_annual) / 365.0
        
        # Create trade
        trade = Trade(
            ticker=ticker,
            entry_date=entry_bar['timestamp'],
            entry_price=entry_price,
            shares=shares,
            initial_margin=required_margin,
            borrow_cost_daily=daily_borrow_cost,
            commission_entry=commission,
            slippage_entry=slippage_cost,
            was_partial_fill=was_partial
        )
        
        # Update cash
        self.cash_available -= total_cost
        
        # Add to open positions
        self.open_positions[ticker] = trade
        
        logger.info(f"ENTER SHORT: {ticker} @ ${entry_price:.2f} x {shares} shares (gap: {gap_pct:.2%}, partial: {was_partial})")
        
        return trade
    
    def exit_position(
        self, 
        ticker: str, 
        exit_bar: Dict,
        reason: str,
        is_forced_liquidation: bool = False
    ) -> Optional[Trade]:
        """
        Exit a short position
        
        Args:
            ticker: Stock ticker
            exit_bar: Bar data for exit
            reason: Reason for exit (profit_target, stop_loss, time_limit, margin_call)
            is_forced_liquidation: Whether this is a forced liquidation
        """
        if ticker not in self.open_positions:
            return None
        
        trade = self.open_positions[ticker]
        
        # Get exit price (bid price, or low of bar as proxy for covering)
        base_price = exit_bar.get('low', exit_bar.get('close'))
        
        # Apply slippage (exit - we're covering/buying)
        exit_price, slippage_cost = self.calculate_slippage(trade.shares, base_price, is_entry=False)
        
        # Calculate commission
        commission = self.calculate_commission(trade.shares, exit_price)
        
        # Calculate days held
        days_held = (exit_bar['timestamp'] - trade.entry_date).days
        if days_held == 0:
            days_held = 1  # At least 1 day for intraday trades
        
        # Calculate total borrow cost
        total_borrow_cost = self.calculate_borrow_cost(trade.shares, trade.entry_price, days_held)
        
        # Calculate P&L
        # Short P&L = (entry_price - exit_price) * shares - costs
        gross_pnl = (trade.entry_price - exit_price) * trade.shares
        total_costs = (trade.commission_entry + commission + 
                      trade.slippage_entry + slippage_cost + 
                      total_borrow_cost)
        net_pnl = gross_pnl - total_costs
        
        # Calculate return percentage
        return_pct = net_pnl / (trade.shares * trade.entry_price)
        
        # Update trade
        trade.exit_date = exit_bar['timestamp']
        trade.exit_price = exit_price
        trade.exit_reason = reason
        trade.commission_exit = commission
        trade.slippage_exit = slippage_cost
        trade.total_borrow_cost = total_borrow_cost
        trade.pnl = net_pnl
        trade.return_pct = return_pct
        trade.days_held = days_held
        trade.was_liquidated = is_forced_liquidation
        
        # Return margin and update capital
        returned_margin = trade.initial_margin
        self.cash_available += returned_margin
        
        # Add/subtract P&L
        self.capital += net_pnl
        self.cash_available += net_pnl
        
        # Move to closed trades
        self.closed_trades.append(trade)
        del self.open_positions[ticker]
        
        logger.info(f"EXIT SHORT: {ticker} @ ${exit_price:.2f} | P&L: ${net_pnl:.2f} ({return_pct:.2%}) | Reason: {reason}")
        
        return trade
    
    def update_open_positions(
        self, 
        current_date: datetime, 
        minute_bars: Dict[str, List[Dict]],
        splits_data: Dict[str, List[Dict]] = None
    ) -> List[Trade]:
        """
        Update all open positions with current prices and check exit conditions
        
        Args:
            current_date: Current date being processed
            minute_bars: Dict of ticker -> list of minute bars for the day
            splits_data: Dict of ticker -> list of split events
        
        Returns:
            List of closed trades
        """
        closed_trades = []
        tickers_to_exit = []
        
        for ticker, trade in self.open_positions.items():
            # Check for splits
            if splits_data and ticker in splits_data:
                for split_event in splits_data[ticker]:
                    split_date = split_event['execution_date']
                    if trade.entry_date < split_date <= current_date:
                        # Check if we haven't already adjusted for this split
                        if not any(s[0] == split_date for s in trade.splits_adjusted):
                            self.apply_split(trade, split_date, split_event['split_ratio'])
            
            # Get minute bars for this ticker
            bars = minute_bars.get(ticker, [])
            if not bars:
                continue
            
            # Check each bar for exit conditions