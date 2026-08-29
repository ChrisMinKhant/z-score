import numpy as np
import pandas as pd
import requests
import yfinance as yf

# ==========================================
# TELEGRAM CONFIGURATION
# ==========================================
TELEGRAM_BOT_TOKEN = "8485387101:AAGqURFlJTFUexDEU9-DmQnG-j9wbuxDdRU"
TELEGRAM_CHAT_ID = "1199956672"


def send_telegram_alert(message: str):
    """Dispatches a formatted text notification via the Telegram Bot API."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✓ Telegram alert transmitted successfully.")
        else:
            print(f"✗ Telegram dispatch failed. Status Code: {response.status_code}")
    except Exception as e:
        print(f"✗ Network failure connecting to Telegram: {e}")


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculates Wilder's Smoothed Average True Range (ATR)."""
    high = df["High"]
    low = df["Low"]
    close = df["Close"].shift(1)

    tr1 = high - low
    tr2 = (high - close).abs()
    tr3 = (low - close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    return tr.ewm(alpha=1 / period, adjust=False).mean()


def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculates Wilder's Average Directional Index (ADX) to filter trending regimes."""
    high = df["High"]
    low = df["Low"]

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr = calculate_atr(df, period)
    plus_di = 100 * (pd.Series(plus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean() / tr)
    minus_di = 100 * (pd.Series(minus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean() / tr)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()
    return adx


def analyze_mean_reversion(
    ticker: str,
    account_balance: float = 200.00,
    risk_pct: float = 0.02,
    lookback: int = 20,
    interval: str = "1h",
    max_leverage: float = 10.0,
    min_stop_pips: float = 18.0,
    max_adx: float = 25.0,
    use_reversal_hook: bool = True,
):
    """
    Institutional Quantitative Statistical Mean Reversion Engine.

    Key Safeguards & Optimizations:
    1. Reversal Hook: Confirms momentum exhaustion before entry (prevents falling-knife entries).
    2. Dynamic ATR Stops with Hard Pip Floor: Eliminates micro-pip stop outs and over-leveraged lots.
    3. Max Account Leverage Cap: Constrains lot size to prevent excessive margin exposure.
    4. ADX Regime Filter: Blocks mean reversion during strong trending/breakout regimes (ADX >= 25).
    5. Daily HTF Trend Filter: Aligns trades with the higher-timeframe macro trend (50 Daily EMA).
    """
    print(f"\n==================================================")
    print(f"Analyzing {ticker} [Optimized Quantitative Engine]")
    print(f"==================================================")

    # 1. Fetch primary execution timeframe data (1H)
    df = yf.download(ticker, period="3mo", interval=interval, progress=False)
    if df.empty or len(df) < (lookback + 50):
        print(f"✗ Failed or insufficient data for {ticker}.")
        return

    # Flatten column MultiIndex if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]

    # 2. Fetch Higher Timeframe (HTF) Daily data for Macro Trend Filter (50 EMA)
    df_daily = yf.download(ticker, period="6mo", interval="1d", progress=False)
    if isinstance(df_daily.columns, pd.MultiIndex):
        df_daily.columns = [col[0] for col in df_daily.columns]

    if len(df_daily) >= 50:
        df_daily["EMA_50"] = df_daily["Close"].ewm(span=50, adjust=False).mean()
        htf_bullish = bool(df_daily["Close"].iloc[-1] > df_daily["EMA_50"].iloc[-1])
        htf_ema50_val = float(df_daily["EMA_50"].iloc[-1])
    else:
        htf_bullish = None
        htf_ema50_val = None

    # 3. Calculate Primary Indicators
    df["Rolling_Mean"] = df["Close"].rolling(window=lookback).mean()
    df["Rolling_Std"] = df["Close"].rolling(window=lookback).std()
    df["Z_Score"] = (df["Close"] - df["Rolling_Mean"]) / df["Rolling_Std"]
    df["ATR"] = calculate_atr(df, period=14)
    df["ADX"] = calculate_adx(df, period=14)

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    current_price = float(latest["Close"])
    curr_z = float(latest["Z_Score"])
    prev_z = float(prev["Z_Score"])
    rolling_mean = float(latest["Rolling_Mean"])
    atr_val = float(latest["ATR"])
    adx_val = float(latest["ADX"]) if not pd.isna(latest["ADX"]) else 20.0

    pip_size = 0.01 if "JPY" in ticker else 0.0001
    atr_pips = atr_val / pip_size

    print(f"Price: {current_price:.5f} | Z-Score: {curr_z:.2f} (Prev: {prev_z:.2f})")
    print(f"ADX (14): {adx_val:.1f} | ATR (14): {atr_pips:.1f} pips | HTF Daily Trend: {'Bullish' if htf_bullish else 'Bearish' if htf_bullish is False else 'N/A'}")

    # 4. Regime Filter: Block if market is strongly trending (ADX >= max_adx)
    if adx_val >= max_adx:
        print(f"⏸ TRADE BLOCKED: Market is in a Strong Trend Regime (ADX = {adx_val:.1f} >= {max_adx}).")
        return

    # 5. Signal Evaluation
    is_buy = False
    is_sell = False

    if use_reversal_hook:
        # Reversal Hook: Confirms price was stretched and is now snapping back
        if prev_z <= -2.0 and curr_z > -2.0:
            is_buy = True
        elif prev_z >= 2.0 and curr_z < 2.0:
            is_sell = True
    else:
        # Standard threshold
        if curr_z <= -2.0:
            is_buy = True
        elif curr_z >= 2.0:
            is_sell = True

    # 6. Apply HTF Trend Filter & Generate Orders
    if is_buy:
        if htf_bullish is False:
            print(f"⏸ BUY BLOCKED by HTF Trend Filter (Price below Daily 50 EMA {htf_ema50_val:.5f}).")
            return
        signal = "🔵 BUY (Mean Reversion Hook)"
        entry_price = current_price

        # Stop Loss: Maximum of 1.5x ATR or minimum pip buffer (prevents micro-stops)
        sl_distance = max(1.5 * atr_val, min_stop_pips * pip_size)
        stop_loss = entry_price - sl_distance

        # Take Profit: Target the mean, ensuring minimum 1.5 R:R
        min_tp_target = entry_price + (1.5 * sl_distance)
        take_profit = max(rolling_mean, min_tp_target)

    elif is_sell:
        if htf_bullish is True:
            print(f"⏸ SELL BLOCKED by HTF Trend Filter (Price above Daily 50 EMA {htf_ema50_val:.5f}).")
            return
        signal = "🔴 SELL (Mean Reversion Hook)"
        entry_price = current_price

        sl_distance = max(1.5 * atr_val, min_stop_pips * pip_size)
        stop_loss = entry_price + sl_distance

        min_tp_target = entry_price - (1.5 * sl_distance)
        take_profit = min(rolling_mean, min_tp_target)

    else:
        print(f"⏸ No Actionable Signal: Z-Score ({curr_z:.2f}) within normal range.")
        return

    # 7. Accurate Pip Value per Standard Lot
    if "JPY" in ticker:
        if ticker.startswith("USD"):
            standard_lot_pip_value = 1000.0 / current_price
        else:
            try:
                usdjpy_price = float(yf.download("USDJPY=X", period="1d", progress=False)["Close"].iloc[-1])
                standard_lot_pip_value = 1000.0 / usdjpy_price
            except Exception:
                standard_lot_pip_value = 6.67
    elif "CAD" in ticker and ticker.startswith("USD"):
        standard_lot_pip_value = 10.0 / current_price
    else:
        standard_lot_pip_value = 10.0

    # 8. Institutional Position Sizing with Leverage Cap
    pips_at_risk = abs(entry_price - stop_loss) / pip_size
    cash_at_risk = account_balance * risk_pct

    # Calculate risk-based lot size
    raw_lot_size = cash_at_risk / (pips_at_risk * standard_lot_pip_value)

    # Calculate maximum permissible lots based on account leverage ceiling
    max_allowed_lots = (account_balance * max_leverage) / 100000.0

    # Final lot sizing: Constrained by risk and max leverage
    calculated_lots = min(raw_lot_size, max_allowed_lots)
    calculated_lots = max(round(calculated_lots, 2), 0.01)

    actual_risk_dollars = pips_at_risk * calculated_lots * standard_lot_pip_value
    effective_leverage = (calculated_lots * 100000.0) / account_balance
    reward_pips = abs(take_profit - entry_price) / pip_size
    rr_ratio = reward_pips / pips_at_risk if pips_at_risk > 0 else 0.0

    print(
        f"✓ Valid Signal: {signal} | Lots: {calculated_lots:.2f} | Leverage: {effective_leverage:.1f}x | "
        f"SL: {pips_at_risk:.1f} pips | TP: {reward_pips:.1f} pips | R:R: {rr_ratio:.2f} | Risk: ${actual_risk_dollars:.2f}"
    )

    # 9. Format Telegram Markdown Alert
    pair_clean = ticker.replace("=X", "")
    htf_str = f"Bullish (Above Daily EMA 50: {htf_ema50_val:.5f})" if htf_bullish else f"Bearish (Below Daily EMA 50: {htf_ema50_val:.5f})" if htf_bullish is False else "N/A"

    tg_message = (
        f"📊 *OPTIMIZED QUANT TRADE SIGNAL*\n"
        f"=============================\n"
        f"*Pair:* `{pair_clean}`\n"
        f"*Action:* {signal}\n"
        f"*Z-Score:* `{curr_z:.2f}` (Hook from `{prev_z:.2f}`)\n"
        f"*Market Regime:* Ranging (ADX: `{adx_val:.1f}` < {max_adx})\n"
        f"*HTF Trend:* `{htf_str}`\n"
        f"-----------------------------\n"
        f"🎯 *Entry:* `{entry_price:.5f}`\n"
        f"🛑 *Stop Loss:* `{stop_loss:.5f}` ({pips_at_risk:.1f} pips)\n"
        f"🏁 *Take Profit:* `{take_profit:.5f}` ({reward_pips:.1f} pips)\n"
        f"⚖️ *Risk/Reward:* `1 : {rr_ratio:.2f}`\n"
        f"-----------------------------\n"
        f"📦 *Position Size:* `{calculated_lots:.2f} Lots`\n"
        f"💵 *Dollar Risk:* `${actual_risk_dollars:.2f}` ({(actual_risk_dollars/account_balance)*100:.1f}%)\n"
        f"🛡️ *Effective Leverage:* `{effective_leverage:.1f}x` (Max: `{max_leverage:.0f}x`)\n"
        f"============================="
    )

    # Dispatch to Telegram
    send_telegram_alert(tg_message)

