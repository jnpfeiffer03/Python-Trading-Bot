# test_RSI.py

import pandas as pd
from binance.client import Client

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

def test_rsi_on_qnt():
    client = Client()
    klines = client.get_historical_klines("QNTUSDT", Client.KLINE_INTERVAL_5MINUTE, "12 hours ago UTC")
    df = pd.DataFrame(klines, columns=['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 
                                       'quote_asset_volume', 'number_of_trades', 
                                       'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
    df['close'] = pd.to_numeric(df['close'])

    # Test 1: less than 14 candles
    short_close = df['close'][:10]
    rsi_short = calculate_rsi(short_close)
    print("Short RSI (should be all NaN):\n", rsi_short)

    # Test 2: normal calculation
    df['RSI'] = calculate_rsi(df['close'])
    print("Last 5 RSI values:")
    print(df[['close', 'RSI']].tail(5))

    # Test 3: Check for any NaN in full RSI series after warmup
    warmup_done = df['RSI'][14:]
    if warmup_done.isna().any():
        print("Warning: NaN in RSI after warmup period!")
    else:
        print("RSI calculation looks good (no NaN after 14th candle).")

if __name__ == '__main__':
    test_rsi_on_qnt()
