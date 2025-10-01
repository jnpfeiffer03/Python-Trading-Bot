# File: main_v3.py

import os
import json
import pandas as pd
from dotenv import load_dotenv
from kucoin.client import User, Trade
from binance.client import Client
from datetime import datetime
import time

# === CONFIG ===
CONFIG_PATH = "config.json"
def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

cfg = load_config()

# Load .env file if present
load_dotenv()

api_key = os.getenv("KUCOIN_API_KEY")
api_secret = os.getenv("KUCOIN_API_SECRET")
api_passphrase = os.getenv("KUCOIN_API_PASSPHRASE")

missing_vars = []
if not api_key:
    missing_vars.append("KUCOIN_API_KEY")
if not api_secret:
    missing_vars.append("KUCOIN_API_SECRET")
if not api_passphrase:
    missing_vars.append("KUCOIN_API_PASSPHRASE")
if missing_vars:
    print(f"\nFATAL: The following required KuCoin API env variables are missing: {', '.join(missing_vars)}")
    print("Please set them in your .env file or environment before running this bot.\n")
    exit(1)

trade_client = Trade(key=api_key, secret=api_secret, passphrase=api_passphrase)
kucoin_user = User(api_key, api_secret, api_passphrase, url='https://openapi-v2.kucoin.com')
binance_client = Client()

binance_symbol = cfg["pair"]
kucoin_symbol = cfg["pair"].replace("USDT", "-USDT")

LOGS_DIR = "logs"
CSV_PATH = os.path.join(LOGS_DIR, "live_trades.csv")
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)
log_rows = []   # Collect trades in memory for now

def calculate_rsi(data, periods=14, ema=True):
    if len(data) < periods:
        print(f"Not enough data to calculate RSI. Data length: {len(data)}")
        return pd.Series([float('nan')] * len(data))
    delta = data.diff(1)
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

def fetch_latest_data(interval):
    try:
        klines = binance_client.get_klines(symbol=binance_symbol, interval=interval, limit=150)
    except Exception as e:
        print(f"Binance API error: {e}")
        return pd.DataFrame()
    if not klines:
        print("No data returned from Binance API")
        return pd.DataFrame()
    data = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_av', 'trades', 'tb_base_av', 'tb_quote_av', 'ignore'])
    data['close'] = pd.to_numeric(data['close'], errors='coerce')
    return data

def fetch_current_price():
    try:
        ticker = binance_client.get_symbol_ticker(symbol=binance_symbol)
        return float(ticker['price'])
    except Exception as e:
        print(f"Price fetch error: {e}")
        return None

def execute_trading_strategy(state, rsi_last_value, current_price, cfg):
    fee_rate = cfg.get("fee_rate", 0.001)
    first_tp_perc = cfg["first_tp_perc"]
    sec_tp_perc = cfg["sec_tp_perc"]
    sl_perc = cfg["sl_perc"]
    rsi_value_1 = cfg["rsi_value_1"]
    rsi_value_2 = cfg["rsi_value_2"]
    buy_rsi_1 = cfg["buy_rsi_1"]
    buy_rsi_2 = cfg["buy_rsi_2"]
    buy_rsi_3 = cfg["buy_rsi_3"]

    # === BUY LOGIC ===
    if state['holdings'] == 0 or (state['holdings'] > 0 and state['tp_1_hit']):
        # Always add any loss carried forward to next buy
        martingale = cfg.get("martingale", True)
        last_loss = abs(state.get('last_realized_loss', 0)) if martingale else 0
        # Use only once, then reset after a buy
        buy_amount = 0
        if rsi_last_value < buy_rsi_1 and not state['bought_buy_1']:
            base_amount = state['bank'] * (0.25 if state['tp_1_hit'] else 0.4)
            
            buy_amount = min(base_amount + last_loss, state['bank'])
            size = (buy_amount * (1 - fee_rate)) / current_price
            try:
                order = trade_client.create_market_order(kucoin_symbol, 'buy', size=size)
                print(f"[{datetime.utcnow()}] Buy1 executed: {order}")
                state['bank'] -= buy_amount
                state['holdings'] += size
                state['buy_price'] = current_price
                state['bought_buy_1'] = True
                print(f"Buy1: Invested {buy_amount:.2f}, Loss Recovery Used: {last_loss:.2f}, Fee Paid: {buy_amount*fee_rate:.4f}")
                state['last_realized_loss'] = 0
            except Exception as e:
                print(f"Buy1 Kucoin error: {e}")

        elif rsi_last_value < buy_rsi_2 and not state['bought_buy_2']:
            base_amount = state['bank'] * 0.5
            buy_amount = min(base_amount + last_loss, state['bank'])
            size = (buy_amount * (1 - fee_rate)) / current_price
            try:
                order = trade_client.create_market_order(kucoin_symbol, 'buy', size=size)
                print(f"[{datetime.utcnow()}] Buy2 executed: {order}")
                state['bank'] -= buy_amount
                state['holdings'] += size
                state['buy_price'] = current_price
                state['bought_buy_2'] = True
                print(f"Buy2: Invested {buy_amount:.2f}, Loss Recovery Used: {last_loss:.2f}, Fee Paid: {buy_amount*fee_rate:.4f}")
                state['last_realized_loss'] = 0
            except Exception as e:
                print(f"Buy2 Kucoin error: {e}")

        elif rsi_last_value < buy_rsi_3 and not state['bought_buy_3']:
            base_amount = state['bank']
            buy_amount = min(base_amount + last_loss, state['bank'])
            size = (buy_amount * (1 - fee_rate)) / current_price
            try:
                order = trade_client.create_market_order(kucoin_symbol, 'buy', size=size)
                print(f"[{datetime.utcnow()}] Buy3 executed: {order}")
                state['bank'] -= buy_amount
                state['holdings'] += size
                state['buy_price'] = current_price
                state['bought_buy_3'] = True
                print(f"Buy3: Invested {buy_amount:.2f}, Loss Recovery Used: {last_loss:.2f}, Fee Paid: {buy_amount*fee_rate:.4f}")
                state['last_realized_loss'] = 0
            except Exception as e:
                print(f"Buy3 Kucoin error: {e}")

    # === SELL LOGIC ===
    if state['holdings'] > 0:
        profit_percent = (current_price - state['buy_price']) / state['buy_price'] * 100
        gross_value = state['holdings'] * current_price
        fee = gross_value * fee_rate
        net_value = gross_value - fee

        # TP1 (partial sell)
        if profit_percent >= first_tp_perc or rsi_last_value > rsi_value_1:
            sell_amount = state['holdings'] * 0.8
            gross_sell = sell_amount * current_price
            fee_sell = gross_sell * fee_rate
            net_sell = gross_sell - fee_sell
            try:
                order = trade_client.create_market_order(kucoin_symbol, 'sell', size=sell_amount)
                print(f"[{datetime.utcnow()}] TP1 SELL executed: {order}")
                state['holdings'] -= sell_amount
                state['bank'] += net_sell
                state['tp_1_hit'] = True
                state['bought_buy_1'] = False
                state['bought_buy_2'] = False
                state['bought_buy_3'] = False
                print(f"TP1: Sold {sell_amount:.4f}, Fee Paid: {fee_sell:.4f}")
            except Exception as e:
                print(f"TP1 SELL error: {e}")

        # TP2 (full sell)
        if profit_percent >= sec_tp_perc or rsi_last_value > rsi_value_2:
            try:
                order = trade_client.create_market_order(kucoin_symbol, 'sell', size=state['holdings'])
                print(f"[{datetime.utcnow()}] TP2 SELL executed: {order}")
                state['bank'] += net_value
                state['holdings'] = 0
                state['tp_1_hit'] = False
                state['bought_buy_1'] = False
                state['bought_buy_2'] = False
                state['bought_buy_3'] = False
                print(f"TP2: Sold all, Fee Paid: {fee:.4f}")
                state['last_realized_loss'] = 0  # Reset loss after TP2/win
            except Exception as e:
                print(f"TP2 SELL error: {e}")

        # STOP LOSS
        loss_percent = (current_price - state['buy_price']) / state['buy_price'] * 100
        if loss_percent <= sl_perc:
            try:
                order = trade_client.create_market_order(kucoin_symbol, 'sell', size=state['holdings'])
                print(f"[{datetime.utcnow()}] STOPLOSS executed: {order}")
                realized_loss = max(state['buy_price'] * state['holdings'] - net_value, 0)
                state['bank'] += net_value
                state['holdings'] = 0
                state['tp_1_hit'] = False
                state['bought_buy_1'] = False
                state['bought_buy_2'] = False
                state['bought_buy_3'] = False
                state['last_realized_loss'] = realized_loss
                print(f"STOPLOSS: Realized loss recorded for recovery: {realized_loss:.2f}, Fee Paid: {fee:.4f}")
            except Exception as e:
                print(f"STOPLOSS error: {e}")
                
def log_trade(ts, action, price, rsi, size, bank, holdings, buy_price, profit_percent, fee_paid, used_loss, last_realized_loss):
    log_rows.append({
        "timestamp": ts,
        "action": action,
        "price": price,
        "RSI": rsi,
        "size": size,
        "bank": bank,
        "holdings": holdings,
        "buy_price": buy_price,
        "profit_percent": profit_percent,
        "fee_paid": fee_paid,
        "used_loss": used_loss,
        "last_realized_loss": last_realized_loss
    })
    # Write log to CSV each time for persistence (or can batch every N trades for speed)
    pd.DataFrame(log_rows).to_csv(CSV_PATH, index=False)

def main():
    interval = cfg.get("timeframe", "5m")
    interval_seconds = 60 * int(interval.replace("m", "")) if "m" in interval else 300
    state = {
        'bank': cfg["initial_bank"],
        'holdings': 0,
        'buy_price': 0,
        'bought_buy_1': False,
        'bought_buy_2': False,
        'bought_buy_3': False,
        'tp_1_hit': False,
        'last_realized_loss': 0
    }
    print("Running the KuCoin QNT bot (v3 with loss recovery and fee simulation)...")
    next_candle_time = datetime.utcnow().timestamp() + (interval_seconds - datetime.utcnow().timestamp() % interval_seconds)
    while True:
        try:
            current_time = datetime.utcnow().timestamp()
            time_until_next_candle = next_candle_time - current_time

            if time_until_next_candle <= 0:
                data = fetch_latest_data(interval)
                if not data.empty and 'close' in data.columns:
                    rsi_values = calculate_rsi(data['close'], periods=cfg["rsi_periods"], ema=cfg["rsi_ema"])
                    rsi_last_closed_candle = rsi_values.iloc[-1] if not rsi_values.empty else None
                    if rsi_last_closed_candle is not None and not pd.isna(rsi_last_closed_candle):
                        current_price = fetch_current_price()
                        if current_price is not None:
                            print(f"[{datetime.utcnow()}] RSI={rsi_last_closed_candle:.2f} | Price={current_price:.2f} | Bank={state['bank']:.2f} | Holdings={state['holdings']:.4f} | LastLoss={state['last_realized_loss']:.2f}")
                            execute_trading_strategy(state, rsi_last_closed_candle, current_price, cfg)
                        else:
                            print("Failed to fetch current price, skipping trading logic.")
                    else:
                        print("RSI invalid or not enough data.")
                else:
                    print("No valid data from Binance API.")
                next_candle_time = datetime.utcnow().timestamp() + (interval_seconds - datetime.utcnow().timestamp() % interval_seconds)
            else:
                print(f"Sleeping for {int(time_until_next_candle)} seconds.")
                time.sleep(max(1, int(time_until_next_candle)))
        except Exception as e:
            print(f"Unexpected error: {e}")
            time.sleep(60)

if __name__ == '__main__':
    main()
