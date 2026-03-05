from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PositionStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"
    MARGIN_CALLED = "margin_called"


@dataclass
class Position:
    """Represents a single short position"""
    ticker: str
    entry_date: datetime
    entry_price: float
    shares: int
    entry_market_cap: float
    commission: float = 0.0
    borrow_rate: float = 0.0  # Annual borrow rate as decimal (e.g., 0.25 for 25%)
    slippage: float = 0.0
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_commission: float = 0.0
    exit_slippage: float = 0.0
    status: PositionStatus = PositionStatus.OPEN
    max_price: float = field(init=False)
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    borrow_fees_accrued: float = 0.0
    forced_liquidation: bool = False
    partial_fills: List[Tuple[datetime, float, int]] = field(default_factory=list)
    split_adjusted: bool = False
    
    def __post_init__(self):
        self.max_price = self.entry_price
        
    @property
    def entry_value(self) -> float:
        """Total value of position at entry (negative for short)"""
        return -(self.shares * self.entry_price + self.commission + self.slippage)
    
    @property
    def exit_value(self) -> float:
        """Total value of position at exit"""
        if self.exit_price is None:
            return 0.0
        return self.shares * self.exit_price + self.exit_commission + self.exit_slippage
    
    @property
    def gross_pnl(self) -> float:
        """P&L before borrow fees"""
        if self.status == PositionStatus.OPEN:
            return self.unrealized_pnl
        return self.realized_pnl
    
    @property
    def net_pnl(self) -> float:
        """P&L after all fees including borrow costs"""
        return self.gross_pnl - self.borrow_fees_accrued
    
    @property
    def return_pct(self) -> float:
        """Return as percentage of entry value"""
        if abs(self.entry_value) < 0.01:
            return 0.0
        return (self.net_pnl / abs(self.entry_value)) * 100
    
    def calculate_unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L at current price"""
        # For short: profit when price goes down
        gross_pnl = self.shares * (self.entry_price - current_price) - self.commission - self.slippage
        return gross_pnl - self.borrow_fees_accrued
    
    def update_max_price(self, price: float):
        """Track maximum price reached for drawdown calculation"""
        if price > self.max_price:
            self.max_price = price
    
    def calculate_borrow_fees(self, current_date: datetime) -> float:
        """Calculate borrow fees accrued from entry to current date"""
        if self.status == PositionStatus.CLOSED and self.exit_date:
            days_held = (self.exit_date - self.entry_date).total_seconds() / 86400
        else:
            days_held = (current_date - self.entry_date).total_seconds() / 86400
        
        position_value = abs(self.shares * self.entry_price)
        daily_rate = self.borrow_rate / 365.0
        fees = position_value * daily_rate * days_held
        self.borrow_fees_accrued = fees
        return fees
    
    def apply_split(self, split_ratio: float):
        """Apply stock split adjustment (e.g., 2.0 for 2-for-1 split, 0.5 for reverse split)"""
        self.shares = int(self.shares * split_ratio)
        self.entry_price = self.entry_price / split_ratio
        if self.exit_price is not None:
            self.exit_price = self.exit_price / split_ratio
        self.max_price = self.max_price / split_ratio
        self.split_adjusted = True
        logger.info(f"Applied {split_ratio} split to {self.ticker} position")


@dataclass
class Trade:
    """Record of a completed trade"""
    ticker: str
    entry_date: datetime
    exit_date: datetime
    entry_price: float
    exit_price: float
    shares: int
    entry_market_cap: float
    gross_pnl: float
    net_pnl: float
    return_pct: float
    borrow_fees: float
    commissions: float
    slippage: float
    max_adverse_price: float
    max_drawdown_pct: float
    holding_period_days: float
    forced_liquidation: bool = False
    
    @property
    def winner(self) -> bool:
        return self.net_pnl > 0


class Portfolio:
    """Manages portfolio of short positions with margin and risk controls"""
    
    def __init__(
        self,
        initial_capital: float,
        max_position_size: float = 0.1,  # Max 10% per position
        margin_requirement: float = 1.5,  # 150% margin requirement (50% initial margin)
        maintenance_margin: float = 1.25,  # 125% maintenance margin
        default_borrow_rate: float = 0.05,  # 5% annual borrow rate
        commission_per_share: float = 0.0,  # Per-share commission
        min_commission: float = 0.0,  # Minimum commission per trade
        default_slippage_pct: float = 0.005,  # 0.5% default slippage for small caps
    ):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.max_position_size = max_position_size
        self.margin_requirement = margin_requirement
        self.maintenance_margin = maintenance_margin
        self.default_borrow_rate = default_borrow_rate
        self.commission_per_share = commission_per_share
        self.min_commission = min_commission
        self.default_slippage_pct = default_slippage_pct
        
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[Trade] = []
        self.equity_curve: List[Tuple[datetime, float]] = []
        self.margin_calls: List[Tuple[datetime, str, float]] = []
        
    @property
    def open_positions(self) -> Dict[str, Position]:
        """Get all open positions"""
        return {k: v for k, v in self.positions.items() if v.status == PositionStatus.OPEN}
    
    @property
    def num_open_positions(self) -> int:
        """Number of currently open positions"""
        return len(self.open_positions)
    
    def calculate_equity(self, current_prices: Dict[str, float], current_date: datetime) -> float:
        """Calculate total portfolio equity including unrealized P&L"""
        equity = self.cash
        
        for ticker, position in self.open_positions.items():
            if ticker in current_prices:
                position.calculate_borrow_fees(current_date)
                position.unrealized_pnl = position.calculate_unrealized_pnl(current_prices[ticker])
                equity += position.unrealized_pnl
        
        return equity
    
    def calculate_margin_used(self, current_prices: Dict[str, float]) -> float:
        """Calculate total margin used by open positions"""
        margin_used = 0.0
        
        for ticker, position in self.open_positions.items():
            if ticker in current_prices:
                current_value = position.shares * current_prices[ticker]
                margin_used += current_value * self.margin_requirement
        
        return margin_used
    
    def calculate_buying_power(self, current_prices: Dict[str, float]) -> float:
        """Calculate available buying power for new positions"""
        margin_used = self.calculate_margin_used(current_prices)
        return self.cash - margin_used
    
    def calculate_position_size(
        self,
        price: float,
        available_capital: float,
        volatility_adjustment: float = 1.0
    ) -> int:
        """
        Calculate position size in shares
        
        Args:
            price: Entry price per share
            available_capital: Available capital for this trade
            volatility_adjustment: Reduce size for higher volatility (0.5 = half size)
        """
        max_position_value = available_capital * self.max_position_size * volatility_adjustment
        margin_adjusted_value = max_position_value / self.margin_requirement
        shares = int(margin_adjusted_value / price)
        return max(shares, 0)
    
    def calculate_commission(self, shares: int) -> float:
        """Calculate commission for trade"""
        commission = shares * self.commission_per_share
        return max(commission, self.min_commission) if commission > 0 else 0.0
    
    def calculate_slippage(
        self,
        price: float,
        shares: int,
        volume: float,
        is_entry: bool = True,
        custom_slippage_pct: Optional[float] = None
    ) -> float:
        """
        Calculate slippage based on liquidity
        
        Args:
            price: Trade price
            shares: Number of shares
            volume: Recent average volume
            is_entry: True for entry, False for exit
            custom_slippage_pct: Override default slippage percentage
        """
        slippage_pct = custom_slippage_pct if custom_slippage_pct is not None else self.default_slippage_pct
        
        # Increase slippage if trade size is large relative to volume
        if volume > 0:
            volume_impact = (shares / volume) * 0.1  # 0.1% per 1% of volume
            slippage_pct += volume_impact
        
        # Higher slippage on entry for small caps (worse fills on gap up)
        if is_entry:
            slippage_pct *= 1.5
        
        trade_value = shares * price
        return trade_value * slippage_pct
    
    def can_open_position(
        self,
        ticker: str,
        price: float,
        shares: int,
        current_prices: Dict[str, float]
    ) -> Tuple[bool, str]:
        """Check if position can be opened given risk limits"""
        # Check if already have position
        if ticker in self.open_positions:
            return False, f"Already have open position in {ticker}"
        
        # Calculate required margin
        position_value = shares * price
        required_margin = position_value * self.margin_requirement
        
        # Check buying power
        buying_power = self.calculate_buying_power(current_prices)
        if buying_power < required_margin:
            return False, f"Insufficient buying power: {buying_power:.2f} < {required_margin:.2f}"
        
        # Check position size limits
        current_equity = self.calculate_equity(current_prices, datetime.now())
        max_position_value = current_equity * self.max_position_size
        if position_value > max_position_value:
            return False, f"Position size exceeds limit: {position_value:.2f} > {max_position_value:.2f}"
        
        return True, "OK"
    
    def open_position(
        self,
        ticker: str,
        entry_date: datetime,
        entry_price: float,
        shares: int,
        market_cap: float,
        volume: float = 0,
        borrow_rate: Optional[float] = None,
        custom_slippage_pct: Optional[float] = None
    ) -> Optional[Position]:
        """Open a new short position"""
        if shares <= 0:
            logger.warning(f"Cannot open position with {shares} shares")
            return None
        
        # Use default borrow rate if not specified
        if borrow_rate is None:
            borrow_rate = self.default_borrow_rate
        
        # Calculate costs
        commission = self.calculate_commission(shares)
        slippage = self.calculate_slippage(entry_price, shares, volume, is_entry=True, custom_slippage_pct=custom_slippage_pct)
        
        # Create position
        position = Position(
            ticker=ticker,
            entry_date=entry_date,
            entry_price=entry_price,
            shares=shares,
            entry_market_cap=market_cap,
            commission=commission,
            borrow_rate=borrow_rate,
            slippage=slippage,
            status=PositionStatus.OPEN
        )
        
        # Update cash (receive proceeds from short sale minus costs)
        proceeds = shares * entry_price
        self.cash += proceeds - commission - slippage
        
        # Store position
        self.positions[ticker] = position
        
        logger.info(
            f"Opened short position: {ticker} {shares} shares @ ${entry_price:.2f} "
            f"(borrow rate: {borrow_rate*100:.1f}%, slippage: ${slippage:.2f})"
        )
        
        return position
    
    def close_position(
        self,
        ticker: str,
        exit_date: datetime,
        exit_price: float,
        volume: float = 0,
        forced: bool = False,
        custom_slippage_pct: Optional[float] = None
    ) -> Optional[Trade]:
        """Close an existing position"""
        if ticker not in self.positions:
            logger.warning(f"No position found for {ticker}")
            return None
        
        position = self.positions[ticker]
        
        if position.status != PositionStatus.OPEN:
            logger.warning(f"Position {ticker} is not open")
            return None
        
        # Calculate exit costs
        exit_commission = self.calculate_commission(position.shares)
        exit_slippage = self.calculate_slippage(
            exit_price,
            position.shares,
            volume,
            is_entry=False,
            custom_slippage_pct=custom_slippage_pct
        )
        
        # Update position
        position.exit_date = exit_date
        position.exit_price = exit_price
        position.exit_commission = exit_commission
        position.exit_slippage = exit_slippage
        position.forced_liquidation = forced
        position.status = PositionStatus.MARGIN_CALLED if forced else PositionStatus.CLOSED
        
        # Calculate final borrow fees
        position.calculate_borrow_fees(exit_date)
        
        # Calculate P&L
        gross_pnl = position.shares * (position.entry_price - exit_price) - position.commission - position.slippage - exit_commission - exit_slippage
        position.realized_pnl = gross_pnl - position.borrow_fees_accrued
        
        # Update cash (pay to cover short)
        cost_to