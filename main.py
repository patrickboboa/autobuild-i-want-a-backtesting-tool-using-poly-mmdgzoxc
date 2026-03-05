#!/usr/bin/env python3
"""
Main CLI application for backtesting short small-cap gap-up strategies.
"""

import argparse
import sys
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import json
from pathlib import Path

from config import Config
from polygon_client import PolygonClient
from screener import GapUpScreener
from strategy import ShortGapUpStrategy
from backtester import Backtester
from portfolio import Portfolio
from analytics import PerformanceAnalytics
from visualizations import BacktestVisualizer
from data_cache import DataCache


class BacktestCLI:
    """Command-line interface for running backtests."""
    
    def __init__(self):
        self.config = Config()
        self.polygon_client = PolygonClient(self.config.polygon_api_key)
        self.data_cache = DataCache(self.config.cache_dir)
        
    def parse_args(self) -> argparse.Namespace:
        """Parse command-line arguments."""
        parser = argparse.ArgumentParser(
            description='Backtest short small-cap gap-up strategies using Polygon data',
            formatter_class=argparse.RawDescriptionHelpFormatter
        )
        
        # Subcommands
        subparsers = parser.add_subparsers(dest='command', help='Command to execute')
        
        # Backtest command
        backtest_parser = subparsers.add_parser('backtest', help='Run a backtest')
        backtest_parser.add_argument('--start-date', required=True, 
                                    help='Start date (YYYY-MM-DD)')
        backtest_parser.add_argument('--end-date', required=True,
                                    help='End date (YYYY-MM-DD)')
        backtest_parser.add_argument('--initial-capital', type=float, default=100000,
                                    help='Initial capital (default: 100000)')
        backtest_parser.add_argument('--max-positions', type=int, default=10,
                                    help='Max concurrent positions (default: 10)')
        backtest_parser.add_argument('--position-size', type=float, default=0.1,
                                    help='Position size as fraction of capital (default: 0.1)')
        
        # Gap criteria
        backtest_parser.add_argument('--min-gap-percent', type=float, default=5.0,
                                    help='Minimum gap up percentage (default: 5.0)')
        backtest_parser.add_argument('--max-gap-percent', type=float, default=50.0,
                                    help='Maximum gap up percentage (default: 50.0)')
        backtest_parser.add_argument('--min-premarket-volume', type=int, default=10000,
                                    help='Minimum premarket volume (default: 10000)')
        
        # Market cap filters
        backtest_parser.add_argument('--min-market-cap', type=float, default=10e6,
                                    help='Minimum market cap in dollars (default: 10M)')
        backtest_parser.add_argument('--max-market-cap', type=float, default=500e6,
                                    help='Maximum market cap in dollars (default: 500M)')
        
        # Entry/Exit rules
        backtest_parser.add_argument('--entry-delay-minutes', type=int, default=5,
                                    help='Minutes to wait after market open before entry (default: 5)')
        backtest_parser.add_argument('--stop-loss-percent', type=float, default=15.0,
                                    help='Stop loss percentage (default: 15.0)')
        backtest_parser.add_argument('--take-profit-percent', type=float, default=5.0,
                                    help='Take profit percentage (default: 5.0)')
        backtest_parser.add_argument('--max-hold-days', type=int, default=5,
                                    help='Maximum holding period in days (default: 5)')
        backtest_parser.add_argument('--use-trailing-stop', action='store_true',
                                    help='Use trailing stop loss')
        backtest_parser.add_argument('--trailing-stop-percent', type=float, default=10.0,
                                    help='Trailing stop percentage (default: 10.0)')
        
        # Cost modeling
        backtest_parser.add_argument('--borrow-cost-annual', type=float, default=25.0,
                                    help='Annual borrow cost percentage (default: 25.0)')
        backtest_parser.add_argument('--borrow-availability', type=float, default=0.7,
                                    help='Probability of shares being available (default: 0.7)')
        backtest_parser.add_argument('--commission-per-share', type=float, default=0.005,
                                    help='Commission per share (default: 0.005)')
        backtest_parser.add_argument('--slippage-bps', type=float, default=50.0,
                                    help='Slippage in basis points (default: 50)')
        
        # Risk management
        backtest_parser.add_argument('--margin-requirement', type=float, default=0.3,
                                    help='Margin requirement ratio (default: 0.3)')
        backtest_parser.add_argument('--maintenance-margin', type=float, default=0.25,
                                    help='Maintenance margin ratio (default: 0.25)')
        backtest_parser.add_argument('--force-liquidation-buffer', type=float, default=1.05,
                                    help='Forced liquidation buffer multiplier (default: 1.05)')
        
        # Execution modeling
        backtest_parser.add_argument('--partial-fill-prob', type=float, default=0.3,
                                    help='Probability of partial fill (default: 0.3)')
        backtest_parser.add_argument('--min-fill-ratio', type=float, default=0.5,
                                    help='Minimum fill ratio for partial fills (default: 0.5)')
        
        # Output options
        backtest_parser.add_argument('--output-dir', default='results',
                                    help='Output directory for results (default: results)')
        backtest_parser.add_argument('--save-trades', action='store_true',
                                    help='Save individual trade details')
        backtest_parser.add_argument('--generate-charts', action='store_true',
                                    help='Generate visualization charts')
        backtest_parser.add_argument('--no-cache', action='store_true',
                                    help='Disable data caching')
        
        # Walk-forward optimization
        backtest_parser.add_argument('--walk-forward', action='store_true',
                                    help='Enable walk-forward validation')
        backtest_parser.add_argument('--in-sample-months', type=int, default=6,
                                    help='In-sample period in months (default: 6)')
        backtest_parser.add_argument('--out-sample-months', type=int, default=1,
                                    help='Out-of-sample period in months (default: 1)')
        
        # Optimize command
        optimize_parser = subparsers.add_parser('optimize', help='Optimize strategy parameters')
        optimize_parser.add_argument('--start-date', required=True,
                                    help='Start date (YYYY-MM-DD)')
        optimize_parser.add_argument('--end-date', required=True,
                                    help='End date (YYYY-MM-DD)')
        optimize_parser.add_argument('--param-file', required=True,
                                    help='JSON file with parameter ranges')
        optimize_parser.add_argument('--optimization-metric', 
                                    choices=['sharpe', 'sortino', 'calmar', 'total_return'],
                                    default='sharpe',
                                    help='Metric to optimize (default: sharpe)')
        optimize_parser.add_argument('--n-trials', type=int, default=100,
                                    help='Number of optimization trials (default: 100)')
        optimize_parser.add_argument('--output-dir', default='optimization_results',
                                    help='Output directory (default: optimization_results)')
        
        # Screen command
        screen_parser = subparsers.add_parser('screen', help='Screen for gap-ups today')
        screen_parser.add_argument('--min-gap-percent', type=float, default=5.0,
                                  help='Minimum gap percentage (default: 5.0)')
        screen_parser.add_argument('--max-gap-percent', type=float, default=50.0,
                                  help='Maximum gap percentage (default: 50.0)')
        screen_parser.add_argument('--min-market-cap', type=float, default=10e6,
                                  help='Minimum market cap (default: 10M)')
        screen_parser.add_argument('--max-market-cap', type=float, default=500e6,
                                  help='Maximum market cap (default: 500M)')
        screen_parser.add_argument('--output-file', help='Save results to CSV file')
        
        # Cache management
        cache_parser = subparsers.add_parser('cache', help='Manage data cache')
        cache_parser.add_argument('--clear', action='store_true',
                                 help='Clear all cached data')
        cache_parser.add_argument('--stats', action='store_true',
                                 help='Show cache statistics')
        
        return parser.parse_args()
    
    def run_backtest(self, args: argparse.Namespace) -> Dict[str, Any]:
        """Run a backtest with specified parameters."""
        print("="*80)
        print("BACKTEST CONFIGURATION")
        print("="*80)
        
        # Parse dates
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
        
        print(f"Period: {start_date.date()} to {end_date.date()}")
        print(f"Initial Capital: ${args.initial_capital:,.2f}")
        print(f"Max Positions: {args.max_positions}")
        print(f"Position Size: {args.position_size*100:.1f}% of capital")
        print(f"Gap Range: {args.min_gap_percent:.1f}% - {args.max_gap_percent:.1f}%")
        print(f"Market Cap Range: ${args.min_market_cap/1e6:.1f}M - ${args.max_market_cap/1e6:.1f}M")
        print(f"Borrow Cost: {args.borrow_cost_annual:.1f}% annual")
        print(f"Borrow Availability: {args.borrow_availability*100:.0f}%")
        print(f"Slippage: {args.slippage_bps:.1f} bps")
        print("="*80)
        print()
        
        # Configure data cache
        if args.no_cache:
            self.data_cache.enabled = False
        
        # Initialize strategy
        strategy_config = {
            'min_gap_percent': args.min_gap_percent,
            'max_gap_percent': args.max_gap_percent,
            'min_premarket_volume': args.min_premarket_volume,
            'min_market_cap': args.min_market_cap,
            'max_market_cap': args.max_market_cap,
            'entry_delay_minutes': args.entry_delay_minutes,
            'stop_loss_percent': args.stop_loss_percent,
            'take_profit_percent': args.take_profit_percent,
            'max_hold_days': args.max_hold_days,
            'use_trailing_stop': args.use_trailing_stop,
            'trailing_stop_percent': args.trailing_stop_percent,
        }
        
        strategy = ShortGapUpStrategy(strategy_config)
        
        # Initialize portfolio
        portfolio_config = {
            'initial_capital': args.initial_capital,
            'max_positions': args.max_positions,
            'position_size': args.position_size,
            'margin_requirement': args.margin_requirement,
            'maintenance_margin': args.maintenance_margin,
            'force_liquidation_buffer': args.force_liquidation_buffer,
        }
        
        portfolio = Portfolio(portfolio_config)
        
        # Initialize screener
        screener = GapUpScreener(
            polygon_client=self.polygon_client,
            data_cache=self.data_cache,
            min_gap_percent=args.min_gap_percent,
            max_gap_percent=args.max_gap_percent,
            min_market_cap=args.min_market_cap,
            max_market_cap=args.max_market_cap,
        )
        
        # Cost configuration
        cost_config = {
            'borrow_cost_annual': args.borrow_cost_annual,
            'borrow_availability': args.borrow_availability,
            'commission_per_share': args.commission_per_share,
            'slippage_bps': args.slippage_bps,
            'partial_fill_prob': args.partial_fill_prob,
            'min_fill_ratio': args.min_fill_ratio,
        }
        
        # Initialize backtester
        backtester = Backtester(
            polygon_client=self.polygon_client,
            data_cache=self.data_cache,
            screener=screener,
            strategy=strategy,
            portfolio=portfolio,
            cost_config=cost_config,
        )
        
        # Run backtest
        if args.walk_forward:
            print("Running walk-forward validation...")
            results = backtester.run_walk_forward(
                start_date=start_date,
                end_date=end_date,
                in_sample_months=args.in_sample_months,
                out_sample_months=args.out_sample_months,
            )
        else:
            print("Running backtest...")
            results = backtester.run(
                start_date=start_date,
                end_date=end_date,
            )
        
        print("\n" + "="*80)
        print("BACKTEST RESULTS")
        print("="*80)
        
        # Analyze results
        analytics = PerformanceAnalytics(results)
        metrics = analytics.calculate_metrics()
        
        # Display key metrics
        self._display_metrics(metrics)
        
        # Save results
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_file = output_dir / f'backtest_{timestamp}.json'
        
        # Prepare results for saving
        save_data = {
            'config': vars(args),
            'metrics': metrics,
            'equity_curve': results['equity_curve'],
            'drawdown_series': results['drawdown_series'],
        }
        
        if args.save_trades:
            save_data['trades'] = results['trades']
        
        with open(results_file, 'w') as f:
            json.dump(save_data, f, indent=2, default=str)
        
        print(f"\nResults saved to: {results_file}")
        
        # Generate visualizations
        if args.generate_charts:
            print("\nGenerating charts...")
            visualizer = BacktestVisualizer(results, metrics)
            chart_file = output_dir / f'charts_{timestamp}.html'
            visualizer.create_dashboard(str(chart_file))