import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass


@dataclass
class PerformanceMetrics:
    """Container for all performance metrics"""
    total_return: float
    total_return_pct: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_duration: int
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    avg_win_pct: float
    avg_loss_pct: float
    largest_win: float
    largest_loss: float
    avg_hold_time_hours: float
    median_hold_time_hours: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    avg_pnl_per_trade: float
    avg_pnl_per_trade_pct: float
    total_borrow_costs: float
    total_slippage_costs: float
    total_commission_costs: float
    net_profit: float
    gross_profit: float
    gross_loss: float
    consecutive_wins_max: int
    consecutive_losses_max: int
    avg_mae: float  # Maximum Adverse Excursion
    avg_mfe: float  # Maximum Favorable Excursion
    kelly_criterion: float
    calmar_ratio: float
    recovery_factor: float
    expectancy: float
    trades_by_hour: Dict[int, int]
    trades_by_day: Dict[str, int]
    pnl_by_month: Dict[str, float]
    underwater_periods: List[Dict[str, Any]]
    forced_liquidations: int
    margin_calls: int
    avg_gap_pct: float
    avg_entry_spread_pct: float
    avg_exit_spread_pct: float


class AnalyticsEngine:
    """Calculate comprehensive performance metrics for backtesting results"""
    
    def __init__(self, risk_free_rate: float = 0.02):
        """
        Initialize analytics engine
        
        Args:
            risk_free_rate: Annual risk-free rate for Sharpe calculation
        """
        self.risk_free_rate = risk_free_rate
    
    def calculate_metrics(
        self,
        trades: List[Dict[str, Any]],
        equity_curve: pd.Series,
        initial_capital: float,
        start_date: datetime,
        end_date: datetime
    ) -> PerformanceMetrics:
        """
        Calculate all performance metrics
        
        Args:
            trades: List of completed trade dictionaries
            equity_curve: Time series of portfolio equity
            initial_capital: Starting capital
            start_date: Backtest start date
            end_date: Backtest end date
            
        Returns:
            PerformanceMetrics object with all calculated metrics
        """
        if not trades or equity_curve.empty:
            return self._empty_metrics()
        
        # Convert trades to DataFrame for easier analysis
        trades_df = pd.DataFrame(trades)
        
        # Basic returns
        total_return = equity_curve.iloc[-1] - initial_capital
        total_return_pct = (total_return / initial_capital) * 100
        
        # Time-adjusted returns
        days = (end_date - start_date).days
        years = days / 365.25
        annualized_return = (((equity_curve.iloc[-1] / initial_capital) ** (1 / years)) - 1) * 100 if years > 0 else 0
        
        # Risk metrics
        sharpe = self._calculate_sharpe_ratio(equity_curve, initial_capital, years)
        sortino = self._calculate_sortino_ratio(equity_curve, initial_capital, years)
        max_dd, max_dd_duration = self._calculate_max_drawdown(equity_curve)
        
        # Win/Loss metrics
        win_rate, winning_trades, losing_trades, breakeven_trades = self._calculate_win_rate(trades_df)
        profit_factor = self._calculate_profit_factor(trades_df)
        
        # Average metrics
        avg_win, avg_loss = self._calculate_avg_win_loss(trades_df)
        avg_win_pct, avg_loss_pct = self._calculate_avg_win_loss_pct(trades_df)
        largest_win, largest_loss = self._calculate_largest_win_loss(trades_df)
        
        # Hold time metrics
        avg_hold_time, median_hold_time = self._calculate_hold_times(trades_df)
        
        # Cost breakdown
        total_borrow = trades_df['borrow_cost'].sum() if 'borrow_cost' in trades_df else 0
        total_slippage = trades_df['slippage_cost'].sum() if 'slippage_cost' in trades_df else 0
        total_commission = trades_df['commission'].sum() if 'commission' in trades_df else 0
        
        # Profit metrics
        gross_profit = trades_df[trades_df['pnl'] > 0]['pnl'].sum() if 'pnl' in trades_df else 0
        gross_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum()) if 'pnl' in trades_df else 0
        net_profit = total_return
        
        # Consecutive wins/losses
        consecutive_wins_max, consecutive_losses_max = self._calculate_consecutive_streaks(trades_df)
        
        # MAE/MFE
        avg_mae = trades_df['mae'].mean() if 'mae' in trades_df else 0
        avg_mfe = trades_df['mfe'].mean() if 'mfe' in trades_df else 0
        
        # Advanced metrics
        kelly = self._calculate_kelly_criterion(trades_df)
        calmar = annualized_return / abs(max_dd) if max_dd != 0 else 0
        recovery = abs(net_profit / max_dd) if max_dd != 0 else 0
        expectancy = self._calculate_expectancy(trades_df)
        
        # Distribution metrics
        trades_by_hour = self._calculate_trades_by_hour(trades_df)
        trades_by_day = self._calculate_trades_by_day(trades_df)
        pnl_by_month = self._calculate_pnl_by_month(trades_df)
        underwater = self._calculate_underwater_periods(equity_curve, initial_capital)
        
        # Risk events
        forced_liquidations = trades_df['forced_liquidation'].sum() if 'forced_liquidation' in trades_df else 0
        margin_calls = trades_df['margin_call'].sum() if 'margin_call' in trades_df else 0
        
        # Entry characteristics
        avg_gap_pct = trades_df['gap_pct'].mean() if 'gap_pct' in trades_df else 0
        avg_entry_spread = trades_df['entry_spread_pct'].mean() if 'entry_spread_pct' in trades_df else 0
        avg_exit_spread = trades_df['exit_spread_pct'].mean() if 'exit_spread_pct' in trades_df else 0
        
        # Per-trade averages
        avg_pnl_per_trade = trades_df['pnl'].mean() if 'pnl' in trades_df else 0
        avg_pnl_per_trade_pct = trades_df['return_pct'].mean() if 'return_pct' in trades_df else 0
        
        return PerformanceMetrics(
            total_return=total_return,
            total_return_pct=total_return_pct,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            max_drawdown_duration=max_dd_duration,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_win_pct=avg_win_pct,
            avg_loss_pct=avg_loss_pct,
            largest_win=largest_win,
            largest_loss=largest_loss,
            avg_hold_time_hours=avg_hold_time,
            median_hold_time_hours=median_hold_time,
            total_trades=len(trades),
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            breakeven_trades=breakeven_trades,
            avg_pnl_per_trade=avg_pnl_per_trade,
            avg_pnl_per_trade_pct=avg_pnl_per_trade_pct,
            total_borrow_costs=total_borrow,
            total_slippage_costs=total_slippage,
            total_commission_costs=total_commission,
            net_profit=net_profit,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            consecutive_wins_max=consecutive_wins_max,
            consecutive_losses_max=consecutive_losses_max,
            avg_mae=avg_mae,
            avg_mfe=avg_mfe,
            kelly_criterion=kelly,
            calmar_ratio=calmar,
            recovery_factor=recovery,
            expectancy=expectancy,
            trades_by_hour=trades_by_hour,
            trades_by_day=trades_by_day,
            pnl_by_month=pnl_by_month,
            underwater_periods=underwater,
            forced_liquidations=int(forced_liquidations),
            margin_calls=int(margin_calls),
            avg_gap_pct=avg_gap_pct,
            avg_entry_spread_pct=avg_entry_spread,
            avg_exit_spread_pct=avg_exit_spread
        )
    
    def _empty_metrics(self) -> PerformanceMetrics:
        """Return empty metrics object"""
        return PerformanceMetrics(
            total_return=0, total_return_pct=0, annualized_return=0,
            sharpe_ratio=0, sortino_ratio=0, max_drawdown=0, max_drawdown_duration=0,
            win_rate=0, profit_factor=0, avg_win=0, avg_loss=0,
            avg_win_pct=0, avg_loss_pct=0, largest_win=0, largest_loss=0,
            avg_hold_time_hours=0, median_hold_time_hours=0,
            total_trades=0, winning_trades=0, losing_trades=0, breakeven_trades=0,
            avg_pnl_per_trade=0, avg_pnl_per_trade_pct=0,
            total_borrow_costs=0, total_slippage_costs=0, total_commission_costs=0,
            net_profit=0, gross_profit=0, gross_loss=0,
            consecutive_wins_max=0, consecutive_losses_max=0,
            avg_mae=0, avg_mfe=0, kelly_criterion=0,
            calmar_ratio=0, recovery_factor=0, expectancy=0,
            trades_by_hour={}, trades_by_day={}, pnl_by_month={},
            underwater_periods=[], forced_liquidations=0, margin_calls=0,
            avg_gap_pct=0, avg_entry_spread_pct=0, avg_exit_spread_pct=0
        )
    
    def _calculate_sharpe_ratio(
        self,
        equity_curve: pd.Series,
        initial_capital: float,
        years: float
    ) -> float:
        """Calculate Sharpe ratio"""
        if len(equity_curve) < 2:
            return 0.0
        
        returns = equity_curve.pct_change().dropna()
        if returns.empty or returns.std() == 0:
            return 0.0
        
        # Annualize based on data frequency
        periods_per_year = 252  # Trading days
        excess_returns = returns - (self.risk_free_rate / periods_per_year)
        
        sharpe = np.sqrt(periods_per_year) * (excess_returns.mean() / returns.std())
        return sharpe
    
    def _calculate_sortino_ratio(
        self,
        equity_curve: pd.Series,
        initial_capital: float,
        years: float
    ) -> float:
        """Calculate Sortino ratio (penalizes only downside volatility)"""
        if len(equity_curve) < 2:
            return 0.0
        
        returns = equity_curve.pct_change().dropna()
        if returns.empty:
            return 0.0
        
        periods_per_year = 252
        excess_returns = returns - (self.risk_free_rate / periods_per_year)
        
        downside_returns = returns[returns < 0]
        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0.0
        
        sortino = np.sqrt(periods_per_year) * (excess_returns.mean() / downside_returns.std())
        return sortino
    
    def _calculate_max_drawdown(
        self,
        equity_curve: pd.Series
    ) -> Tuple[float, int]:
        """
        Calculate maximum drawdown and its duration
        
        Returns:
            Tuple of (max_drawdown, duration_in_days)
        """
        if equity_curve.empty:
            return 0.0, 0
        
        # Calculate running maximum
        running_max = equity_curve.expanding().max()
        drawdown = equity_curve - running_max
        drawdown_pct = (drawdown / running_max) * 100
        
        max_dd = drawdown_pct.min()
        
        # Calculate drawdown duration
        is_underwater = drawdown < 0
        underwater_periods = []
        start_idx = None
        
        for idx, underwater in enumerate(is_underwater):
            if underwater and start_idx is None:
                start_idx = idx
            elif not underwater and start_idx is not None:
                underwater_periods.append(idx - start_idx)
                start_idx = None
        
        # Handle case where drawdown extends to end
        if start_idx is not None:
            underwater_periods.append(len(is_underwater) - start_idx)
        
        max_duration = max(underwater_periods) if underwater_periods else 0
        
        return max_dd, max_duration
    
    def _calculate_win_rate(
        self,
        trades_df: pd.DataFrame
    ) -> Tuple[float, int, int, int]:
        """Calculate win rate and trade counts"""
        if 'pnl' not in trades_df or trades_df.empty:
            return 0.0, 0, 0, 0
        
        winning = (trades_df['pnl'] > 0).sum()
        losing = (trades_df['pnl'] < 0).sum()
        breakeven = (trades_df['pnl'] == 0).sum()
        
        total = len(trades_df)
        win_rate = (winning / total * 100) if total > 0 else 0.0
        
        return win_rate, int(winning), int(losing), int(breakeven)
    
    def _calculate_profit_factor(self, trades_df: pd.DataFrame) -> float:
        """Calculate profit factor (gross profit / gross loss)"""