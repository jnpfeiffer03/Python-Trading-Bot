import os
import json
import pandas as pd
import itertools
from binance.client import Client
from backtesting import calculate_rsi, backtest_strategy, load_config, download_data

LOGS_DIR = "logs"
RESULTS_CSV = os.path.join(LOGS_DIR, "optimization_results.csv")

if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

# Load data & config (reuse from backtesting_V3.0.py)
cfg = load_config()
print(f"Downloading data for {cfg['pair']} {cfg['timeframe']} from {cfg['starting_date']} to {cfg['ending_date']}")
data = download_data(cfg["pair"], cfg["timeframe"], cfg["starting_date"], cfg["ending_date"])

# --- Parameter grids (customize as needed!) ---
buy_rsi_1_vals = [28.5, 29, 29.5, 30]
buy_rsi_2_vals = [27, 27.5, 28, 28.5]
buy_rsi_3_vals = [26, 26.5, 27]
sl_vals        = [-1.5, -2, -2.5]
tp1_vals       = [0.8, 1, 1.2]
tp2_vals       = [1.2, 1.5, 2]
rsi_periods    = [12, 14, 16]
rsi_ema_vals   = [True, False]
martingale_vals = [True, False]

results = []
tested = 0

# --- Grid Search ---
for params in itertools.product(
    buy_rsi_1_vals, buy_rsi_2_vals, buy_rsi_3_vals,
    sl_vals, tp1_vals, tp2_vals, rsi_periods, rsi_ema_vals, martingale_vals):

    buy_rsi_1, buy_rsi_2, buy_rsi_3, sl, tp1, tp2, rsi_p, rsi_ema, martingale = params
    cfg_test = cfg.copy()
    cfg_test['buy_rsi_1'] = buy_rsi_1
    cfg_test['buy_rsi_2'] = buy_rsi_2
    cfg_test['buy_rsi_3'] = buy_rsi_3
    cfg_test['sl_perc'] = sl
    cfg_test['first_tp_perc'] = tp1
    cfg_test['sec_tp_perc'] = tp2
    cfg_test['rsi_periods'] = rsi_p
    cfg_test['rsi_ema'] = rsi_ema
    cfg_test['martingale'] = martingale

    # Calculate RSI for this setting
    data['RSI'] = calculate_rsi(data['close'], periods=rsi_p, ema=rsi_ema)
    logs, stats = backtest_strategy(data, cfg_test)
    results.append({
        "RSI1": buy_rsi_1, "RSI2": buy_rsi_2, "RSI3": buy_rsi_3,
        "SL": sl, "TP1": tp1, "TP2": tp2,
        "rsi_periods": rsi_p, "rsi_ema": rsi_ema, "martingale": martingale,
        "ROI": stats["roi"], "WinRate": stats["winrate"],
        "Profit": stats["profit_loss"], "Drawdown": stats["max_drawdown"]
    })
    tested += 1
    if tested % 20 == 0:
        print(f"Tested {tested} combinations...")

print(f"Done. Tested {tested} parameter combinations.")

# Save all results to CSV
df = pd.DataFrame(results)
df.to_csv(RESULTS_CSV, index=False)
print(f"Results saved to {RESULTS_CSV}")

# Print top 10 by ROI
top_roi = df.sort_values("ROI", ascending=False).head(10)
print("\n=== Top 10 by ROI ===")
print(top_roi[["RSI1", "RSI2", "RSI3", "SL", "TP1", "TP2", "rsi_periods", "rsi_ema", "martingale", "ROI", "WinRate", "Profit", "Drawdown"]])

# Print top 10 by WinRate
top_win = df.sort_values("WinRate", ascending=False).head(10)
print("\n=== Top 10 by WinRate ===")
print(top_win[["RSI1", "RSI2", "RSI3", "SL", "TP1", "TP2", "rsi_periods", "rsi_ema", "martingale", "ROI", "WinRate", "Profit", "Drawdown"]])
