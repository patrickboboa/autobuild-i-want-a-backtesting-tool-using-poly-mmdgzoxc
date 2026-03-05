import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.gridspec import GridSpec
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import seaborn as sns
from pathlib import Path


class BacktestVisualizer:
    """Generate comprehensive visualization suite for backtest results."""
    
    def __init__(self, output_dir: str = "output"):
        """Initialize visualizer with output directory."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Set style
        plt.style.use('seaborn-v0_8-darkgrid')
        sns.set_palette("husl")
        
    def plot_equity_curve(self, equity_series: pd.Series, benchmark: Optional[pd.Series] = None,
                         title: str = "Portfolio Equity Curve", save_name: str = "equity_curve.png") -> None:
        """Plot equity curve with optional benchmark comparison."""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), height_ratios=[3, 1])
        
        # Main equity curve
        ax1.plot(equity_series.index, equity_series.values, label='Strategy', linewidth=2, color='#2E86AB')
        
        if benchmark is not None:
            ax1.plot(benchmark.index, benchmark.values, label='Benchmark', 
                    linewidth=1.5, color='#A23B72', linestyle='--', alpha=0.7)
        
        ax1.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax1.set_ylabel('Portfolio Value ($)', fontsize=12, fontweight='bold')
        ax1.legend(loc='upper left', fontsize=11)
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Add statistics box
        total_return = (equity_series.iloc[-1] / equity_series.iloc[0] - 1) * 100
        max_val = equity_series.max()
        min_val = equity_series.min()
        
        stats_text = f'Total Return: {total_return:.2f}%\nMax Value: ${max_val:,.0f}\nMin Value: ${min_val:,.0f}'
        ax1.text(0.02, 0.98, stats_text, transform=ax1.transAxes, 
                fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        # Daily returns distribution
        returns = equity_series.pct_change().dropna()
        ax2.hist(returns * 100, bins=50, color='#2E86AB', alpha=0.7, edgecolor='black')
        ax2.axvline(returns.mean() * 100, color='red', linestyle='--', linewidth=2, label=f'Mean: {returns.mean()*100:.3f}%')
        ax2.axvline(returns.median() * 100, color='green', linestyle='--', linewidth=2, label=f'Median: {returns.median()*100:.3f}%')
        ax2.set_xlabel('Daily Returns (%)', fontsize=11, fontweight='bold')
        ax2.set_ylabel('Frequency', fontsize=11, fontweight='bold')
        ax2.set_title('Daily Returns Distribution', fontsize=12, fontweight='bold')
        ax2.legend(fontsize=9)
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / save_name, dpi=300, bbox_inches='tight')
        plt.close()
        
    def plot_drawdown(self, equity_series: pd.Series, title: str = "Drawdown Analysis",
                     save_name: str = "drawdown.png") -> None:
        """Plot drawdown chart with underwater equity curve."""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), height_ratios=[2, 1])
        
        # Calculate drawdown
        cumulative = equity_series
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max * 100
        
        # Plot equity with running max
        ax1.plot(cumulative.index, cumulative.values, label='Equity', linewidth=2, color='#2E86AB')
        ax1.plot(running_max.index, running_max.values, label='Running Maximum', 
                linewidth=1.5, color='#F18F01', linestyle='--', alpha=0.7)
        ax1.fill_between(cumulative.index, cumulative.values, running_max.values, 
                        where=(cumulative.values <= running_max.values), 
                        color='red', alpha=0.3, label='Drawdown')
        ax1.set_title(title, fontsize=16, fontweight='bold', pad=20)
        ax1.set_ylabel('Portfolio Value ($)', fontsize=12, fontweight='bold')
        ax1.legend(loc='upper left', fontsize=11)
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Drawdown percentage
        ax2.fill_between(drawdown.index, 0, drawdown.values, color='#C1121F', alpha=0.6)
        ax2.plot(drawdown.index, drawdown.values, color='#780000', linewidth=1.5)
        ax2.set_xlabel('Date', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Drawdown (%)', fontsize=12, fontweight='bold')
        ax2.set_title('Underwater Equity Curve', fontsize=12, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Add max drawdown annotation
        max_dd = drawdown.min()
        max_dd_date = drawdown.idxmin()
        ax2.annotate(f'Max DD: {max_dd:.2f}%', 
                    xy=(max_dd_date, max_dd), 
                    xytext=(10, 20), 
                    textcoords='offset points',
                    bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.7),
                    arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0', color='red', lw=2),
                    fontsize=10, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(self.output_dir / save_name, dpi=300, bbox_inches='tight')
        plt.close()
        
    def plot_trade_distribution(self, trades: List[Dict], save_name: str = "trade_distribution.png") -> None:
        """Plot comprehensive trade distribution analysis."""
        if not trades:
            print("No trades to plot")
            return
            
        fig = plt.figure(figsize=(16, 12))
        gs = GridSpec(3, 3, figure=fig, hspace=0.3, wspace=0.3)
        
        # Extract trade data
        returns_pct = [t.get('return_pct', 0) for t in trades]
        pnl = [t.get('pnl', 0) for t in trades]
        holding_periods = [t.get('holding_period_days', 0) for t in trades]
        entry_gaps = [t.get('gap_percent', 0) for t in trades if 'gap_percent' in t]
        slippage_costs = [t.get('slippage_cost', 0) for t in trades if 'slippage_cost' in t]
        borrow_costs = [t.get('borrow_cost', 0) for t in trades if 'borrow_cost' in t]
        
        # 1. Returns distribution histogram
        ax1 = fig.add_subplot(gs[0, :2])
        ax1.hist(returns_pct, bins=50, color='#2E86AB', alpha=0.7, edgecolor='black')
        ax1.axvline(0, color='red', linestyle='--', linewidth=2, label='Break-even')
        ax1.axvline(np.mean(returns_pct), color='green', linestyle='--', linewidth=2, 
                   label=f'Mean: {np.mean(returns_pct):.2f}%')
        ax1.set_xlabel('Return per Trade (%)', fontsize=11, fontweight='bold')
        ax1.set_ylabel('Frequency', fontsize=11, fontweight='bold')
        ax1.set_title('Trade Returns Distribution', fontsize=13, fontweight='bold')
        ax1.legend(fontsize=10)
        ax1.grid(True, alpha=0.3)
        
        # 2. Win/Loss pie chart
        ax2 = fig.add_subplot(gs[0, 2])
        wins = sum(1 for r in returns_pct if r > 0)
        losses = sum(1 for r in returns_pct if r < 0)
        breakeven = sum(1 for r in returns_pct if r == 0)
        
        sizes = [wins, losses, breakeven]
        labels = [f'Wins: {wins}', f'Losses: {losses}', f'BE: {breakeven}']
        colors = ['#28a745', '#dc3545', '#ffc107']
        
        wedges, texts, autotexts = ax2.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%',
                                           startangle=90, textprops={'fontsize': 9, 'fontweight': 'bold'})
        ax2.set_title('Win/Loss Ratio', fontsize=12, fontweight='bold')
        
        # 3. P&L distribution
        ax3 = fig.add_subplot(gs[1, 0])
        ax3.hist(pnl, bins=50, color='#6A4C93', alpha=0.7, edgecolor='black')
        ax3.axvline(0, color='red', linestyle='--', linewidth=2)
        ax3.set_xlabel('P&L ($)', fontsize=11, fontweight='bold')
        ax3.set_ylabel('Frequency', fontsize=11, fontweight='bold')
        ax3.set_title('P&L Distribution', fontsize=12, fontweight='bold')
        ax3.grid(True, alpha=0.3)
        
        # 4. Holding period distribution
        ax4 = fig.add_subplot(gs[1, 1])
        ax4.hist(holding_periods, bins=30, color='#F18F01', alpha=0.7, edgecolor='black')
        ax4.axvline(np.mean(holding_periods), color='red', linestyle='--', linewidth=2,
                   label=f'Mean: {np.mean(holding_periods):.1f} days')
        ax4.set_xlabel('Holding Period (days)', fontsize=11, fontweight='bold')
        ax4.set_ylabel('Frequency', fontsize=11, fontweight='bold')
        ax4.set_title('Holding Period Distribution', fontsize=12, fontweight='bold')
        ax4.legend(fontsize=9)
        ax4.grid(True, alpha=0.3)
        
        # 5. Cumulative P&L
        ax5 = fig.add_subplot(gs[1, 2])
        cumulative_pnl = np.cumsum(pnl)
        ax5.plot(range(len(cumulative_pnl)), cumulative_pnl, linewidth=2, color='#2E86AB')
        ax5.fill_between(range(len(cumulative_pnl)), 0, cumulative_pnl, 
                        where=(np.array(cumulative_pnl) >= 0), color='green', alpha=0.3)
        ax5.fill_between(range(len(cumulative_pnl)), 0, cumulative_pnl, 
                        where=(np.array(cumulative_pnl) < 0), color='red', alpha=0.3)
        ax5.set_xlabel('Trade Number', fontsize=11, fontweight='bold')
        ax5.set_ylabel('Cumulative P&L ($)', fontsize=11, fontweight='bold')
        ax5.set_title('Cumulative P&L Over Trades', fontsize=12, fontweight='bold')
        ax5.grid(True, alpha=0.3)
        
        # 6. Entry gap distribution
        if entry_gaps:
            ax6 = fig.add_subplot(gs[2, 0])
            ax6.hist(entry_gaps, bins=30, color='#C1121F', alpha=0.7, edgecolor='black')
            ax6.axvline(np.mean(entry_gaps), color='blue', linestyle='--', linewidth=2,
                       label=f'Mean: {np.mean(entry_gaps):.2f}%')
            ax6.set_xlabel('Gap Up %', fontsize=11, fontweight='bold')
            ax6.set_ylabel('Frequency', fontsize=11, fontweight='bold')
            ax6.set_title('Entry Gap Distribution', fontsize=12, fontweight='bold')
            ax6.legend(fontsize=9)
            ax6.grid(True, alpha=0.3)
        
        # 7. Slippage costs
        if slippage_costs:
            ax7 = fig.add_subplot(gs[2, 1])
            ax7.hist(slippage_costs, bins=30, color='#8B4513', alpha=0.7, edgecolor='black')
            ax7.axvline(np.mean(slippage_costs), color='red', linestyle='--', linewidth=2,
                       label=f'Mean: ${np.mean(slippage_costs):.2f}')
            ax7.set_xlabel('Slippage Cost ($)', fontsize=11, fontweight='bold')
            ax7.set_ylabel('Frequency', fontsize=11, fontweight='bold')
            ax7.set_title('Slippage Cost Distribution', fontsize=12, fontweight='bold')
            ax7.legend(fontsize=9)
            ax7.grid(True, alpha=0.3)
        
        # 8. Borrow costs
        if borrow_costs:
            ax8 = fig.add_subplot(gs[2, 2])
            ax8.hist(borrow_costs, bins=30, color='#4A0E4E', alpha=0.7, edgecolor='black')
            ax8.axvline(np.mean(borrow_costs), color='red', linestyle='--', linewidth=2,
                       label=