import numpy as np
import pandas as pd
import requests
import yfinance as yf

# ==========================================
# TELEGRAM CONFIGURATION
# Replace these strings with your active credentials
# ==========================================
TELEGRAM_BOT_TOKEN = "8485387101:AAGqURFlJTFUexDEU9-DmQnG-j9wbuxDdRU"
TELEGRAM_CHAT_ID = "1199956672"


def send_telegram_alert(message):
    """Dispatches a formatted text notification via the Telegram Bot API."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",  # Allows bolding and code blocks in alerts
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✓ Telegram alert transmitted successfully.")
        else:
            print(f"✗ Telegram dispatch failed. Status Code: {response.status_code}")
    except Exception as e:
        print(f"✗ Network failure connection to Telegram: {e}")


def analyze_mean_reversion(ticker, account_balance, risk_pct=0.02, lookback=20, interval="1h"):
    print(f"Analyzing {ticker} using Statistical Mean Reversion...")

    # Fetch 3 months of data to ensure we have enough bars to calculate the 200 MA on both 1h and 4h intervals
    df = yf.download(ticker, period="3mo", interval=interval)
    if df.empty:
        print(f"✗ Failed to download data for {ticker}.")
        return

    df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]

    # Calculate indicators
    df["Rolling_Mean"] = df["Close"].rolling(window=lookback).mean()
    df["Rolling_Std"] = df["Close"].rolling(window=lookback).std()
    df["Z_Score"] = (df["Close"] - df["Rolling_Mean"]) / df["Rolling_Std"]
    df["MA_200"] = df["Close"].rolling(window=200).mean()

    latest = df.iloc[-1]
    current_price = float(latest["Close"])
    z_score = float(latest["Z_Score"])
    rolling_std = float(latest["Rolling_Std"])
    ma_200 = float(latest["MA_200"]) if not pd.isna(latest["MA_200"]) else None

    # Trend filter verification
    # Only take buy signals if the current price is above the 200 MA
    # Only take sell signals if the current price is below the 200 MA
    is_above_ma200 = ma_200 is None or current_price > ma_200
    is_below_ma200 = ma_200 is None or current_price < ma_200

    # Evaluate Signals
    if z_score <= -2.0:
        if not is_above_ma200:
            print(f"Current Z-Score: {z_score:.2f} (Oversold). BUY blocked by Trend Filter (Price {current_price:.5f} <= MA 200 {ma_200:.5f}).")
            return
        signal = "🔵 BUY (Oversold Mean Reversion)"
        entry_price = current_price
        stop_loss = df["Rolling_Mean"].iloc[-1] - (3.0 * rolling_std)
        take_profit = float(df["Rolling_Mean"].iloc[-1])
    elif z_score >= 2.0:
        if not is_below_ma200:
            print(f"Current Z-Score: {z_score:.2f} (Overbought). SELL blocked by Trend Filter (Price {current_price:.5f} >= MA 200 {ma_200:.5f}).")
            return
        signal = "🔴 SELL (Overbought Mean Reversion)"
        entry_price = current_price
        stop_loss = df["Rolling_Mean"].iloc[-1] + (3.0 * rolling_std)
        take_profit = float(df["Rolling_Mean"].iloc[-1])
    else:
        print(f"Current Z-Score: {z_score:.2f}. Market within normal range.")
        return

    # Pip configuration
    pip_size = 0.01 if "JPY" in ticker else 0.0001
    
    # Calculate standard lot pip value in USD (assuming USD account)
    if "JPY" in ticker:
        # Standard lot pip value in JPY is 1,000 JPY. Convert to USD using the USDJPY exchange rate.
        if ticker.startswith("USD"):
            standard_lot_pip_value = 1000.0 / current_price
        else:
            try:
                # Fetch USDJPY rate to convert JPY-denominated pip value to USD
                usdjpy_price = float(yf.download("USDJPY=X", period="1d")["Close"].iloc[-1])
                standard_lot_pip_value = 1000.0 / usdjpy_price
            except Exception:
                standard_lot_pip_value = 6.67 # Fallback approximation (assuming USDJPY ~ 150)
    else:
        standard_lot_pip_value = 10.0

    # Position Sizing
    stop_loss_distance = abs(entry_price - stop_loss)
    pips_at_risk = stop_loss_distance / pip_size
    cash_at_risk = account_balance * risk_pct

    # Formula Correction: Raw lot size is cash_at_risk divided by (pips_at_risk * standard_lot_pip_value).
    # The previous formula incorrectly multiplied by pip_size in the denominator, inflating the lot size by 10,000x.
    raw_lot_size = cash_at_risk / (pips_at_risk * standard_lot_pip_value)
    calculated_lots = np.floor(raw_lot_size * 100) / 100

    print(
        f"Signal: {calculated_lots:.2f} Lots | Risk: ${cash_at_risk:.2f} | Pips at Risk: {pips_at_risk:.1f}"
    )

    if calculated_lots < 0.01:
        calculated_lots = 0.01
        # Formula Correction: Actual risk is pips_at_risk * calculated_lots * standard_lot_pip_value.
        actual_risk = pips_at_risk * calculated_lots * standard_lot_pip_value
        risk_status = f"⚠️ Risk expands to ${actual_risk:.2f} ({(actual_risk/account_balance)*100:.1f}%) due to min lot rules."
    else:
        risk_status = "✓ Risk matches safe portfolio parameters."

    # Build clean Telegram markdown message
    pair_clean = ticker.replace("=X", "")
    ma_200_str = f"{ma_200:.5f}" if ma_200 is not None else "N/A"
    
    tg_message = (
        f"📊 *TRADE EXECUTION SIGNAL*\n"
        f"=============================\n"
        f"*Pair:* `{pair_clean}`\n"
        f"*Action:* {signal}\n"
        f"*Z-Score:* `{z_score:.2f}`\n"
        f"*MA 200:* `{ma_200_str}`\n"
        f"-----------------------------\n"
        f"🎯 *Entry Limit:* `{entry_price:.5f}`\n"
        f"🛑 *Stop Loss:* `{stop_loss:.5f}` ({pips_at_risk:.1f} pips)\n"
        f"🏁 *Take Profit:* `{take_profit:.5f}`\n"
        f"-----------------------------\n"
        f"📦 *Position Size:* `{calculated_lots:.2f} Lots`\n"
        f"💵 *Allotted Risk:* `${cash_at_risk:.2f}`\n"
        f"🛡️ *Safety Check:* {risk_status}\n"
        f"============================="
    )

    # Dispatch to device
    send_telegram_alert(tg_message)
