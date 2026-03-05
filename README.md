# Small Cap Gap-Up Short Backtesting Tool

A comprehensive backtesting system for testing short-selling strategies on small-cap stocks that gap up at market open. Built with Polygon.io premium data access and realistic market microstructure assumptions.

## Overview

This tool enables rigorous backtesting of mean-reversion strategies targeting small-cap stocks that experience significant overnight gaps. It addresses common backtesting pitfalls including survivorship bias, look-ahead bias, unrealistic execution assumptions, and the unique challenges of shorting illiquid securities.

## Features

- **Realistic Market Microstructure**
  - Configurable hard-to-borrow (HTB) fees for small-cap shorts
  - Bid-ask spread modeling with slippage on illiquid stocks
  - Partial fill simulation for large positions relative to volume
  - Execution delays modeling realistic order routing times

- **Historical Universe Integrity**
  - Tests against full historical ticker universe including delisted stocks
  - Avoids survivorship bias by including failed companies
  - Handles corporate actions (splits, reverse splits, delistings)
  - Point-in-time market cap calculations

- **Risk Management**
  - Margin requirement tracking
  - Forced liquidation simulation on margin calls
  - Overnight gap risk exposure monitoring
  - Position sizing based on available capital and margin

- **Advanced Analytics**
  - Walk-forward optimization to prevent overfitting
  - Multiple performance metrics (Sharpe, Sortino, Max DD, Calmar)
  - Trade-by-trade analysis with exit reason classification
  - Time-series equity curves and drawdown charts

## Prerequisites

- Python 3.9 or higher
- Polygon.io Premium subscription (required for minute-level data and full ticker universe)
- Replit account (optional, for cloud deployment)

## Installation

### Local Setup

1. Clone or download the project files

2. Install dependencies:
```
pip install -r requirements.txt
```

3. Configure environment variables:
```
cp .env.example .env
```

4. Edit `.env` and add your Polygon.io API key:
```
POLYGON_API_KEY=your_api_key_here
```

### Replit Setup

1. Import project to Replit
2. Add Secret: `POLYGON_API_KEY` with your API key
3. Run the project using the Run button

## Configuration

Edit `config.py` to customize default settings:

### Data Settings
- `START_DATE`: Backtest start date
- `END_DATE`: Backtest end date
- `MIN_MARKET_CAP`: Minimum market cap in dollars (e.g., 10M for small caps)
- `MAX_MARKET_CAP`: Maximum market cap in dollars (e.g., 300M for small caps)
- `CACHE_ENABLED`: Enable/disable local data caching

### Strategy Parameters

#### Gap Identification
- `MIN_GAP_PERCENT`: Minimum overnight gap size (e.g., 5.0 for 5%)
- `MAX_GAP_PERCENT`: Maximum overnight gap size to avoid extreme situations (e.g., 50.0)
- `GAP_CALCULATION_METHOD`: 'close_to_open' or 'close_to_high_of_first_bar'

#### Entry Criteria
- `MIN_VOLUME`: Minimum daily volume required (e.g., 100000 shares)
- `MIN_DOLLAR_VOLUME`: Minimum dollar volume (e.g., $500k)
- `ENTRY_DELAY_MINUTES`: Minutes to wait after market open before entry (e.g., 1-5)
- `MAX_SPREAD_PERCENT`: Maximum bid-ask spread as % of mid (e.g., 5.0)
- `SLIPPAGE_MODEL`: 'fixed' or 'volume_based' or 'spread_based'
- `ENTRY_SLIPPAGE_BPS`: Entry slippage in basis points (e.g., 50 = 0.5%)

#### Position Sizing
- `POSITION_SIZE_METHOD`: 'fixed_dollar', 'fixed_percent', 'volatility_adjusted', or 'volume_based'
- `DEFAULT_POSITION_SIZE`: Dollar amount per position (e.g., 10000)
- `MAX_POSITION_PERCENT`: Max % of portfolio per position (e.g., 10.0)
- `MAX_POSITION_VOLUME_PERCENT`: Max % of average daily volume per position (e.g., 2.0)

#### Exit Rules
- `PROFIT_TARGET_PERCENT`: Take profit level (e.g., 3.0 for 3% gain on short)
- `STOP_LOSS_PERCENT`: Stop loss level (e.g., 15.0 for 15% adverse move)
- `TRAILING_STOP_PERCENT`: Trailing stop distance (e.g., 5.0, or null to disable)
- `TIME_STOP_MINUTES`: Maximum hold time in minutes (e.g., 240 for 4 hours)
- `EXIT_AT_CLOSE`: Force exit at market close (true/false)
- `EXIT_SLIPPAGE_BPS`: Exit slippage in basis points

#### Borrowing Costs
- `HTB_FEE_ANNUAL_PERCENT`: Annual hard-to-borrow fee rate (e.g., 15.0 for 15% APR)
- `BORROW_AVAILABILITY_RATE`: Probability that shares are available to borrow (e.g., 0.7 for 70%)
- `HTB_FEE_CALCULATION`: 'daily' or 'by_position_duration'

#### Risk Management
- `INITIAL_CAPITAL`: Starting capital (e.g., 100000)
- `MARGIN_REQUIREMENT`: Short margin requirement as decimal (e.g., 1.5 for 150%)
- `MAINTENANCE_MARGIN`: Maintenance margin requirement (e.g., 1.3 for 130%)
- `MARGIN_CALL_BUFFER`: Buffer before forced liquidation (e.g., 0.05 for 5%)
- `MAX_CONCURRENT_POSITIONS`: Maximum number of simultaneous shorts (e.g., 10)

## Usage

### Basic Backtest

Run a backtest with default parameters:

```
python main.py
```

### Custom Date Range

```
python main.py --start-date 2022-01-01 --end-date 2023-12-31
```

### Custom Strategy Parameters

```
python main.py --min-gap 8.0 --profit-target 5.0 --stop-loss 20.0
```

### Walk-Forward Optimization

```
python main.py --optimize --optimization-method walk_forward --in-sample-months 12 --out-sample-months 3
```

### Save Results

```
python main.py --output results/my_backtest.json --save-trades --save-plots
```

## Strategy Parameters Explained

### Gap Criteria

**MIN_GAP_PERCENT** (default: 5.0)
- Minimum overnight gap to qualify for short entry
- Higher values target more extreme gaps (potentially stronger mean reversion)
- Lower values increase sample size but may reduce edge
- Recommended range: 3.0 - 15.0

**MAX_GAP_PERCENT** (default: 50.0)
- Filters out extreme gaps that may indicate material news events
- Prevents shorting into buyout announcements, FDA approvals, etc.
- Very large gaps (>50%) often have fundamental catalysts and don't revert
- Recommended range: 30.0 - 100.0

### Execution Timing

**ENTRY_DELAY_MINUTES** (default: 1)
- Wait time after market open before entering short
- Accounts for order routing, liquidity aggregation, and price discovery
- Smaller values capture more of the gap but risk poor fills
- Larger values miss some reversion but improve execution quality
- Recommended range: 1 - 10 minutes

**TIME_STOP_MINUTES** (default: 240)
- Maximum holding period before forced exit
- Intraday strategies should exit before close to avoid overnight risk
- Longer holds capture more complete reversions but increase risk
- Recommended range: 60 - 360 minutes (1-6 hours)

### Exit Targets

**PROFIT_TARGET_PERCENT** (default: 3.0)
- Percentage price decline (gain for short) before taking profit
- Balance between win rate and average winner size
- Small targets (2-4%) increase win rate but limit upside
- Large targets (8-15%) reduce win rate but capture full reversions
- Recommended range: 2.0 - 10.0

**STOP_LOSS_PERCENT** (default: 15.0)
- Percentage price increase (loss for short) before cutting position
- Critical for managing risk on continued gap-up momentum
- Should be wider than typical gap size to avoid premature stops
- Too wide risks catastrophic losses on squeeze scenarios
- Recommended range: 10.0 - 30.0

**TRAILING_STOP_PERCENT** (default: null)
- Distance to trail stop below highest favorable price (lowest price for shorts)
- Locks in profits while allowing room for volatility
- More aggressive than fixed profit targets
- Recommended range: 3.0 - 8.0 or disabled

### Position Sizing

**POSITION_SIZE_METHOD**

- **fixed_dollar**: Every position is DEFAULT_POSITION_SIZE (e.g., $10k)
  - Simple and consistent
  - Doesn't account for volatility or available capital
  
- **fixed_percent**: Position size = portfolio equity × DEFAULT_POSITION_SIZE / 100
  - Scales with account size
  - Compounds gains and losses
  
- **volatility_adjusted**: Size inversely proportional to recent volatility
  - Reduces size in more volatile stocks
  - Aims for consistent risk per trade
  
- **volume_based**: Size limited by average daily volume
  - Prevents oversizing illiquid names
  - Critical for realistic small-cap modeling

**MAX_POSITION_VOLUME_PERCENT** (default: 2.0)
- Maximum position size as percentage of average daily volume
- Ensures realistic position sizes relative to liquidity
- Exiting 2% of daily volume minimizes market impact
- Lower values for more conservative execution assumptions
- Recommended range: 1.0 - 5.0

### Borrowing Costs

**HTB_FEE_ANNUAL_PERCENT** (default: 15.0)
- Annual interest rate for borrowing hard-to-borrow shares
- Small caps often have high borrow costs (10-50% APR)
- Significantly impacts profitability on longer holds
- Check real-time borrow costs via Interactive Brokers or similar
- Recommended range: 10.0 - 50.0

**BORROW_AVAILABILITY_RATE** (default: 0.7)
- Probability that shares are available to short
- Small caps often have limited borrow availability
- Prevents overstating strategy capacity
- Lower values for more conservative assumptions
- Recommended range: 0.5 - 0.9

### Risk Controls

**MARGIN_REQUIREMENT** (default: 1.5)
- Initial margin required as multiple of position value
- Reg T requirement is 1.5 for stocks (150% of value)
- Cannot short more than available margin allows
- Limits portfolio leverage

**MARGIN_CALL_BUFFER** (default: 0.05)
- Cushion before forced liquidation (5% = liquidate at 105% of maintenance margin)
- Accounts for slippage during forced covering
- Simulates realistic broker risk management
- Recommended range: 0.03 - 0.10

### Market Microstructure

**SLIPPAGE_MODEL**

- **fixed**: Apply ENTRY_SLIPPAGE_BPS to every trade
  - Simple but unrealistic
  - Use for quick sensitivity analysis
  
- **volume_based**: Slippage increases with position size relative to volume
  - More realistic for small caps
  - Larger positions relative to volume get worse fills
  
- **spread_based**: Slippage based on bid-ask spread width
  - Most realistic for illiquid stocks
  - Accounts for actual liquidity constraints

**MAX_SPREAD_PERCENT** (default: 5.0)
- Maximum bid-ask spread (as % of mid) allowed for entry
- Filters out extremely illiquid stocks
- Prevents unrealistic fills on wide markets
- Recommended range: 3.0 - 10.0

## Interpreting Results

### Performance Metrics

**Total Return**
- Overall percentage gain/loss from initial capital
- Compare to S&P 500 return over same period for context

**Sharpe Ratio**
- Risk-adjusted return (excess return / volatility)
- Above 1.0 is decent, above 2.0 is excellent for daily trading
- Negative values indicate losses or high volatility relative to returns

**Sortino Ratio**
- Similar to Sharpe but only penalizes downside volatility
- Better metric for asymmetric strategies
- Higher values indicate better risk-adjusted returns

**Maximum Drawdown**
- Largest peak-to-trough decline in portfolio value
- Critical for understanding worst-case scenario
- Should be compared to initial capital to assess survivability

**Calmar Ratio**
- Annual return / Maximum drawdown
- Above 1.0 is acceptable, above 3.0 is excellent
- Balances return with worst-case risk

**Win Rate**
- Percentage of profitable trades
- Mean reversion strategies typically have 50-70% win rates
- Low win rate (<40%) may indicate flawed strategy logic

**Average Win / Average Loss Ratio**
- Measures asymmetry in trade outcomes
- Should be >1.5 to compensate for <50% win rate
- Lower values require higher win rates for profitability

**Profit Factor**
- Gross profits / Gross losses
- Must be >1.0 for profitability
- Above 1.5 is good, above 2.0 is excellent

### Trade Analysis

**Exit Reason Distribution**
- **Profit Target**: Strategy worked as intended
- **Stop Loss**: Trade went against position
- **Time Stop**: Exit at time limit (may indicate lack of mean reversion)
- **Market Close**: Forced exit to avoid overnight risk
- **Margin Call**: Position closed due to margin constraint (bad sign)

High percentage of margin calls indicates insufficient risk management or excessive leverage.

Majority of time stops may indicate profit target is unrealistic or gap reversions take longer.

### Trade Statistics

**Trades Per Year**
- Frequency of opportunities
- Too few (<20/year) may not provide statistical significance
- Too many (>500/year) may indicate overfitting or execution challenges

**Average Holding Time**
- Typical duration from entry to exit
- Should align with TIME_STOP_MINUTES
- Very short holds (<30min) indicate quick reversions or stop-outs

**Average Position Size**
- Typical dollar value per trade
- Should scale with capital available
- Verify it respects liquidity constraints (volume limits)

**Slippage Impact**
- Total cost of execution inefficiency
- High slippage (>1% per trade) may make strategy unprofitable
- Indicates need for tighter filters or improved execution

**HTB Fees Paid**
- Total borrowing costs
- Significant expense for holding shorts overnight or in high-HTB-fee stocks
- Should be less than 20% of gross profits for viability

### Equity Curve Analysis

**Smooth Uptrend**
- Indicates consistent edge with low variance
- Ideal scenario for strategy deployment

**Stepped Growth**
- Periods of gains followed by flat periods
- May indicate regime dependence (works in certain market conditions)

**Extended Drawdowns**
- Long periods without new equity highs
- Could indicate market regime change or strategy decay
- Assess whether drawdown recovered or persists

**Volatile Equity Curve**
- Large swings between profit and loss
- High risk even if long-term return is positive
- May be psychologically difficult to trade

### Warning Signs

- Win rate <35%: Strategy logic may be flawed or parameters too aggressive
- Average loss > 2× average win: Risk/reward imbalance
- Maximum drawdown >40% of initial capital: Unsustainable risk
- Sharpe ratio <0.5: Poor risk-adjusted returns
- Most exits via margin call: Insufficient capital or excessive leverage
- Negative correlation between position size and return: Liquidity issues
- All profits from first year then flat: Overfitting or regime change

## Walk-Forward Optimization

To avoid overfitting, use walk-forward analysis