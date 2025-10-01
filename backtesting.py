# File: backtesting.py

import os
import json
import pandas as pd
from binance.client import Client

CONFIG_PATH = "config.json"
LOGS_DIR = "logs"
CSV_PATH = os.path.join(LOGS_DIR, "backtesting.csv")

def load_config():
    # Load settings from config.json, else use defaults.
    defaults = {
        "pair": "QNTUSDT",
        "timeframe": "5m",
        "starting_date": "1 January 2024",
        "ending_date": "30 December 2024",
        "initial_bank": 1000,
        "fee_rate": 0.0001,
        "rsi_periods": 14,
        "rsi_ema": True,
        "first_tp_perc": 1,
        "sec_tp_perc": 1.5,
        "sl_perc": -1,
        "rsi_value_1": 42.5,
        "rsi_value_2": 55,
        "buy_rsi_1": 29.5,
        "buy_rsi_2": 28.5,
        "buy_rsi_3": 27
    }
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            user = json.load(f)
        for k in defaults:
            if k not in user:
                user[k] = defaults[k]
        return user
    else:
        print("config.json not found, using defaults!")
        return defaults

def download_data(pair, timeframe, starting_date, ending_date):
    client = Client()
    klines = client.get_historical_klines(pair, timeframe, starting_date, ending_date)
    data = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'])
    data = data[['timestamp', 'close']]
    data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
    data['close'] = pd.to_numeric(data['close'])
    return data

def calculate_rsi(series, periods=14, ema=True):
    if len(series) < periods:
        return pd.Series([float('nan')] * len(series), index=series.index)
    delta = series.diff(1)
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    if ema:
        avg_gain = gain.ewm(com=periods-1, min_periods=periods, adjust=False).mean()
        avg_loss = loss.ewm(com=periods-1, min_periods=periods, adjust=False).mean()
    else:
        avg_gain = gain.rolling(window=periods, min_periods=periods).mean()
        avg_loss = loss.rolling(window=periods, min_periods=periods).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def backtest_strategy(data, cfg):
    # === STATE ===
    state = {
        "bank": cfg["initial_bank"],
        "holdings": 0,
        "buy_price": 0,
        "bought_buy_1": False,
        "bought_buy_2": False,
        "bought_buy_3": False,
        "tp_1_hit": False,
        "last_realized_loss": 0,
        "wins": 0,
        "losses": 0,
        "max_drawdown": 0,
        "last_peak": cfg["initial_bank"]
    }
    fee_rate = cfg.get("fee_rate", 0.001)
    log_rows = []
    for i, row in data.iterrows():
        rsi = row['RSI']
        price = row['close']
        ts = row['timestamp']
        action = None
        trade_size = 0
        profit_percent = 0
        fee_paid = 0
        used_loss = 0

        # BUY LOGIC (with loss recovery)
        if state['holdings'] == 0 or (state['holdings'] > 0 and state['tp_1_hit']):
            martingale = cfg.get("martingale", True)
            last_loss = abs(state.get('last_realized_loss', 0)) if martingale else 0
            used_loss = last_loss
            buy_amount = 0
            if rsi < cfg["buy_rsi_1"] and not state['bought_buy_1']:
                base_amount = state['bank'] * (0.25 if state['tp_1_hit'] else 0.4)
                buy_amount = min(base_amount + last_loss, state['bank'])
                size = (buy_amount * (1 - fee_rate)) / price
                state['bank'] -= buy_amount
                state['holdings'] += size
                state['buy_price'] = price
                state['bought_buy_1'] = True
                fee_paid = buy_amount * fee_rate
                action = "BUY1"
                trade_size = size
                state['last_realized_loss'] = 0
            elif rsi < cfg["buy_rsi_2"] and not state['bought_buy_2']:
                base_amount = state['bank'] * 0.5
                buy_amount = min(base_amount + last_loss, state['bank'])
                size = (buy_amount * (1 - fee_rate)) / price
                state['bank'] -= buy_amount
                state['holdings'] += size
                state['buy_price'] = price
                state['bought_buy_2'] = True
                fee_paid = buy_amount * fee_rate
                action = "BUY2"
                trade_size = size
                state['last_realized_loss'] = 0
            elif rsi < cfg["buy_rsi_3"] and not state['bought_buy_3']:
                base_amount = state['bank']
                buy_amount = min(base_amount + last_loss, state['bank'])
                size = (buy_amount * (1 - fee_rate)) / price
                state['bank'] -= buy_amount
                state['holdings'] += size
                state['buy_price'] = price
                state['bought_buy_3'] = True
                fee_paid = buy_amount * fee_rate
                action = "BUY3"
                trade_size = size
                state['last_realized_loss'] = 0

        # SELL LOGIC
        if state['holdings'] > 0:
            profit_percent = (price - state['buy_price']) / state['buy_price'] * 100
            gross_value = state['holdings'] * price
            fee = gross_value * fee_rate
            net_value = gross_value - fee
            # TP1 (partial sell)
            if profit_percent >= cfg["first_tp_perc"] or rsi > cfg["rsi_value_1"]:
                sell_amount = state['holdings'] * 0.8
                gross_sell = sell_amount * price
                fee_sell = gross_sell * fee_rate
                net_sell = gross_sell - fee_sell
                state['holdings'] -= sell_amount
                state['bank'] += net_sell
                state['tp_1_hit'] = True
                state['bought_buy_1'] = False
                state['bought_buy_2'] = False
                state['bought_buy_3'] = False
                fee_paid = fee_sell
                action = "TP1"
                trade_size = sell_amount
            # TP2 (full sell)
            if profit_percent >= cfg["sec_tp_perc"] or rsi > cfg["rsi_value_2"]:
                sell_amount = state['holdings']
                gross_sell = sell_amount * price
                fee_sell = gross_sell * fee_rate
                net_sell = gross_sell - fee_sell
                state['bank'] += net_sell
                state['holdings'] = 0
                state['tp_1_hit'] = False
                state['bought_buy_1'] = False
                state['bought_buy_2'] = False
                state['bought_buy_3'] = False
                fee_paid = fee_sell
                action = "TP2"
                trade_size = sell_amount
                # Win/loss and loss carry
                if profit_percent > 0:
                    state['wins'] += 1
                    state['last_realized_loss'] = 0  # reset loss after win
                else:
                    # Loss at TP2, add to loss carry
                    realized_loss = max(state['buy_price'] * sell_amount - net_sell, 0)
                    state['losses'] += 1
                    state['last_realized_loss'] = realized_loss
            # STOP LOSS
            loss_percent = (price - state['buy_price']) / state['buy_price'] * 100
            if loss_percent <= cfg["sl_perc"]:
                sell_amount = state['holdings']
                gross_sell = sell_amount * price
                fee_sell = gross_sell * fee_rate
                net_sell = gross_sell - fee_sell
                realized_loss = max(state['buy_price'] * sell_amount - net_sell, 0)
                state['bank'] += net_sell
                state['holdings'] = 0
                state['tp_1_hit'] = False
                state['bought_buy_1'] = False
                state['bought_buy_2'] = False
                state['bought_buy_3'] = False
                fee_paid = fee_sell
                action = "STOPLOSS"
                trade_size = sell_amount
                state['losses'] += 1
                state['last_realized_loss'] = realized_loss

        # Drawdown tracking
        total_value = state['bank'] + state['holdings'] * price
        if total_value > state['last_peak']:
            state['last_peak'] = total_value
        dd = (total_value - state['last_peak']) / state['last_peak'] * 100
        if dd < state['max_drawdown']:
            state['max_drawdown'] = dd

        # Log the trade
        if action is not None:
            log_rows.append({
                "timestamp": ts,
                "action": action,
                "price": price,
                "RSI": rsi,
                "size": trade_size,
                "bank": state['bank'],
                "holdings": state['holdings'],
                "buy_price": state['buy_price'],
                "profit_percent": profit_percent,
                "fee_paid": fee_paid,
                "used_loss": used_loss,
                "last_realized_loss": state.get('last_realized_loss', 0)
            })

    # Final PnL stats
    final_value = state['bank'] + state['holdings'] * data.iloc[-1]['close']
    profit_loss = final_value - cfg["initial_bank"]
    roi = profit_loss / cfg["initial_bank"]
    winrate = state['wins'] / (state['wins'] + state['losses']) if (state['wins'] + state['losses']) > 0 else 0

    summary = {
        "profit_loss": profit_loss,
        "roi": roi,
        "winrate": winrate,
        "wins": state['wins'],
        "losses": state['losses'],
        "max_drawdown": state['max_drawdown']
    }
    return log_rows, summary

def main():
    cfg = load_config()
    if not os.path.exists(LOGS_DIR):
        os.makedirs(LOGS_DIR)
    print(f"Loading data for {cfg['pair']} {cfg['timeframe']} from {cfg['starting_date']} to {cfg['ending_date']}")
    data = download_data(cfg["pair"], cfg["timeframe"], cfg["starting_date"], cfg["ending_date"])
    data['RSI'] = calculate_rsi(data['close'], periods=cfg["rsi_periods"], ema=cfg["rsi_ema"])
    print("Running backtest...")
    logs, stats = backtest_strategy(data, cfg)
    pd.DataFrame(logs).to_csv(CSV_PATH, index=False)
    print(f"Backtest log written to {CSV_PATH}")
    print("=== Backtest Summary ===")
    print(f"Profit/Loss: {stats['profit_loss']:.2f}")
    print(f"ROI: {stats['roi']*100:.2f}%")
    print(f"WinRate: {stats['winrate']*100:.2f}%")
    print(f"Wins: {stats['wins']} | Losses: {stats['losses']}")
    print(f"Max Drawdown: {stats['max_drawdown']:.2f}%")

if __name__ == '__main__':
    main()
