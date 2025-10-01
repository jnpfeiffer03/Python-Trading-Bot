fork from: https://github.com/asier13/Python-Trading-Bot/

This project is a modular, production-grade cryptocurrency trading bot and backtesting suite for KuCoin (using QNT/USDT, but adaptable to any pair), with:

    • Live trading (with state recovery, fee simulation, and loss recovery/Martingale option)
    • Backtesting with identical logic
    • Parameter grid search optimizer for RSI, TP, SL, Martingale
    • Easy configuration via config.json and .env
    • All trades, state, and optimizations logged to /logs for audit and quant research

Features
    • Live Trading: Fully automated, with persistent state, trade logs, and instant resume after power/network loss.
    • Backtesting: Accurate simulation, fee deduction, loss recovery logic, and performance stats.
    • Optimization: Grid search for best RSI/TP/SL/Martingale settings, results to CSV for analysis.
    • Loss Recovery/Martingale: Can be enabled or disabled in config.json.
    • Safe API usage: All secrets are stored in .env.
    • Pro-style Logging: All trades and optimizer runs are saved to CSV files for future review.
    • Crash-Resistant: Bot resumes from latest state after restart.
    • Extensible: All configs, pairs, and strategy logic can be adjusted for any coin/exchange.

Directory Structure:

├── strategy.py            # Main live trading bot (KuCoin)
├── backtesting.py     	   # Backtest your logic over historical data
├── optimize_params.py     # Grid search optimizer for parameters
├── config.json             # All strategy settings (pair, TP, SL, RSI, Martingale, etc.)
├── .env                    # Your KuCoin API keys (never commit this file!)
├── requirements.txt        # All Python dependencies
└── logs/
    ├── live_trades.csv     # All live trades, in detail
    ├── live_state.json     # Last known bot state (auto resume)
    ├── backtesting.csv     # All simulated backtest trades
    └── optimization_results.csv  # Grid search results (best params, ROI, winrate, etc.)

Quick Start

1. Install Requirements
pip install -r requirements.txt

2. Set Up .env
Create a .env file in your repo (never share or commit this):
KUCOIN_API_KEY=your_key_here
KUCOIN_API_SECRET=your_secret_here
KUCOIN_API_PASSPHRASE=your_passphrase_here

3. Edit config.json
All settings are in this file. Example:
{
    "pair": "QNTUSDT",
    "timeframe": "5m",
    "starting_date": "1 January 2024",
    "ending_date": "30 December 2024",
    "initial_bank": 500,
    "fee_rate": 0.001,
    "martingale": true,      // Set to false for fixed size after loss
    "rsi_periods": 14,
    "rsi_ema": true,
    "first_tp_perc": 1,
    "sec_tp_perc": 1.5,
    "sl_perc": -2,
    "rsi_value_1": 42.5,
    "rsi_value_2": 55,
    "buy_rsi_1": 29.5,
    "buy_rsi_2": 28.5,
    "buy_rsi_3": 27
}

Change pair or strategy values as needed.

4. Live Trading (with KuCoin)
Start the bot:
python3 strategy.py

State is saved: You can stop/restart any time, and the bot resumes exactly where it left off.
All trades and state: Logged in /logs/live_trades.csv and /logs/live_state.json.

5. Backtesting
Backtest any config (identical to live trading logic):
python3 backtesting.py

See /logs/backtesting.csv for full trade log.
Summary stats printed at end (ROI, winrate, drawdown, etc.)

6. Parameter Optimization
Test 100s or 1000s of strategies to find the best RSI, SL, TP, and Martingale settings:
python3 optimize_params.py

All results in /logs/optimization_results.csv
Top 10 by ROI/Winrate shown in terminal
Use pandas/Excel/Jupyter to further analyze or plot best settings

7. Key Features & Safety
    • Martingale (Loss Recovery): Toggle in config.json (martingale: true/false).
    • State Resume: Full auto-resume after any interruption (no manual editing needed).
    • Logging: Every trade, every state update, every optimization saved in /logs.
    • Fee Simulation: Realistic trading, with exchange fees deducted on every trade.
    • Risk: Test your settings! Martingale can magnify wins AND risks. Use with caution.

8. Extending or Customizing
    • You can swap out pair, intervals, strategy logic, or API endpoints as needed.
    • To support other coins/exchanges, adjust symbol formats and endpoints in config/code.
    • All bot logic is modular and well-commented for ease of further development.

Disclaimer
Crypto trading is risky.
This bot is for research and educational use only.
No warranty is provided. Use with paper trading and backtesting before live deployment!

Trade smart, test everything, and always control your risk. 🚀
