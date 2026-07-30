import numpy as np
import pandas as pd
import requests
import yfinance as yf

# Try to import MetaTrader 5 library (pymt5linux on Linux, or native MetaTrader5 on Windows)
try:
    from pymt5linux import MetaTrader5 as mt5_class
    MT5_AVAILABLE = True
    IS_LINUX_WRAPPER = True
except ImportError:
    try:
        import MetaTrader5 as mt5_module
        MT5_AVAILABLE = True
        IS_LINUX_WRAPPER = False
    except ImportError:
        MT5_AVAILABLE = False
        IS_LINUX_WRAPPER = False

if MT5_AVAILABLE:
    mt5_ref = mt5_class if IS_LINUX_WRAPPER else mt5_module
else:
    mt5_ref = None


def get_mt5_connection():
    """Returns an initialized MT5 connection instance.
    
    For pymt5linux (Linux), it returns a new instance of MetaTrader5().
    For native MetaTrader5 (Windows), it returns the mt5 module.
    """
    if not MT5_AVAILABLE:
        return None
    if IS_LINUX_WRAPPER:
        try:
            return mt5_class()
        except Exception as e:
            print(f"⚠️ Failed to connect to pymt5linux Wine RPC server: {e}")
            return None
    else:
        return mt5_module

# ==========================================
# TELEGRAM CONFIGURATION
# Replace these strings with your active credentials
# ==========================================
TELEGRAM_BOT_TOKEN = "8485387101:AAGqURFlJTFUexDEU9-DmQnG-j9wbuxDdRU"
TELEGRAM_CHAT_ID = "1199956672"

# ==========================================
# METATRADER 5 CONFIGURATION
# Replace these with your MT5 account credentials if required.
# If MT5 is already logged in on your system, you can leave these as None.
# ==========================================
MT5_LOGIN = None       # e.g., 12345678 (must be an integer)
MT5_PASSWORD = None    # e.g., "your_password" (string)
MT5_SERVER = None      # e.g., "Your-Broker-Server" (string)
MT5_PATH = None        # e.g., "C:\\Program Files\\MetaTrader 5\\terminal64.exe" (string)


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


def place_mt5_order(symbol, order_type, entry_price, stop_loss, take_profit, lots):
    """Connects to MetaTrader 5 and places a pending limit order.
    
    Returns a status string detailing the outcome.
    """
    if not MT5_AVAILABLE:
        msg = "⚠️ MetaTrader 5 Python library is not available on this platform."
        print(msg)
        return msg

    # Initialize connection
    conn = None
    try:
        conn = get_mt5_connection()
        if conn is None:
            return "❌ Failed to connect to MT5 (could not establish RPC client connection)."
    except Exception as e:
        msg = f"❌ Exception establishing MT5 connection: {e}"
        print(msg)
        return msg

    # Initialize connection
    init_success = False
    try:
        # Check if login details are configured
        if MT5_LOGIN is not None and MT5_PASSWORD is not None and MT5_SERVER is not None:
            init_kwargs = {
                "login": int(MT5_LOGIN),
                "password": MT5_PASSWORD,
                "server": MT5_SERVER,
            }
            if MT5_PATH is not None:
                init_kwargs["path"] = MT5_PATH
            init_success = conn.initialize(**init_kwargs)
        else:
            if MT5_PATH is not None:
                init_success = conn.initialize(path=MT5_PATH)
            else:
                init_success = conn.initialize()
    except Exception as e:
        msg = f"❌ Exception during MT5 initialization: {e}"
        print(msg)
        return msg

    if not init_success:
        error_code = conn.last_error()
        msg = f"❌ MT5 initialization failed. Error code: {error_code}"
        print(msg)
        return msg

    try:
        # Select symbol
        if not conn.symbol_select(symbol, True):
            error_code = conn.last_error()
            msg = f"❌ Failed to select symbol '{symbol}' in MT5. Error code: {error_code}"
            print(msg)
            return msg

        # Fetch symbol info
        symbol_info = conn.symbol_info(symbol)
        if symbol_info is None:
            msg = f"❌ Symbol '{symbol}' not found in MT5."
            print(msg)
            return msg

        # Retrieve digits to round prices correctly
        digits = symbol_info.digits
        price_rounded = round(entry_price, digits)
        sl_rounded = round(stop_loss, digits)
        tp_rounded = round(take_profit, digits)

        # Retrieve/resolve filling mode
        filling_mode = symbol_info.filling_mode
        if (filling_mode & 1) != 0:
            type_filling = mt5_ref.ORDER_FILLING_FOK
        elif (filling_mode & 2) != 0:
            type_filling = mt5_ref.ORDER_FILLING_IOC
        else:
            type_filling = mt5_ref.ORDER_FILLING_RETURN

        # Map our simplified order types to MT5 pending types
        # order_type should be "BUY" or "SELL"
        if order_type == "BUY":
            mt5_order_type = mt5_ref.ORDER_TYPE_BUY_LIMIT
            action_desc = "Buy Limit"
        elif order_type == "SELL":
            mt5_order_type = mt5_ref.ORDER_TYPE_SELL_LIMIT
            action_desc = "Sell Limit"
        else:
            msg = f"❌ Invalid order type: {order_type}"
            print(msg)
            return msg

        # Create trade request
        request = {
            "action": mt5_ref.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": float(lots),
            "type": mt5_order_type,
            "price": price_rounded,
            "sl": sl_rounded,
            "tp": tp_rounded,
            "deviation": 10,
            "magic": 123456,
            "comment": "Antigravity Z-Score Bot",
            "type_time": mt5_ref.ORDER_TIME_GTC,
            "type_filling": type_filling,
        }

        # Send order
        result = conn.order_send(request)

        if result is None:
            error_code = conn.last_error()
            msg = f"❌ MT5 order_send returned None. Error code: {error_code}"
            print(msg)
            return msg

        if result.retcode != mt5_ref.TRADE_RETCODE_DONE:
            msg = f"❌ MT5 Order failed. Retcode: {result.retcode} ({result.comment})"
            print(msg)
            return msg

        msg = (
            f"✅ *Order Placed Successfully!*\n"
            f"🎫 *Ticket:* `{result.order}`\n"
            f"📈 *Action:* `{action_desc}` at `{price_rounded:.{digits}f}`\n"
            f"🛑 *Stop Loss:* `{sl_rounded:.{digits}f}`\n"
            f"🏁 *Take Profit:* `{tp_rounded:.{digits}f}`"
        )
        print(f"✓ MT5 Order placed successfully. Ticket: {result.order}")
        return msg

    finally:
        try:
            conn.shutdown()
        except Exception:
            pass


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
        order_direction = "BUY"
        entry_price = current_price
        stop_loss = df["Rolling_Mean"].iloc[-1] - (3.0 * rolling_std)
        take_profit = float(df["Rolling_Mean"].iloc[-1])
    elif z_score >= 2.0:
        if not is_below_ma200:
            print(f"Current Z-Score: {z_score:.2f} (Overbought). SELL blocked by Trend Filter (Price {current_price:.5f} >= MA 200 {ma_200:.5f}).")
            return
        signal = "🔴 SELL (Overbought Mean Reversion)"
        order_direction = "SELL"
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

    # Clean pair symbol
    pair_clean = ticker.replace("=X", "")

    # Position Sizing
    stop_loss_distance = abs(entry_price - stop_loss)
    pips_at_risk = stop_loss_distance / pip_size
    cash_at_risk = account_balance * risk_pct

    # Formula Correction: Raw lot size is cash_at_risk divided by (pips_at_risk * standard_lot_pip_value).
    raw_lot_size = cash_at_risk / (pips_at_risk * standard_lot_pip_value)
    
    # Try to adjust lot sizing based on MT5 symbol rules if MT5 is available and initialized
    mt5_adjusted = False
    if MT5_AVAILABLE:
        try:
            conn = get_mt5_connection()
            if conn is not None and conn.initialize():
                if conn.symbol_select(pair_clean, True):
                    symbol_info = conn.symbol_info(pair_clean)
                    if symbol_info is not None:
                        volume_step = symbol_info.volume_step
                        volume_min = symbol_info.volume_min
                        volume_max = symbol_info.volume_max
                        
                        # Round down to volume step
                        calculated_lots = np.floor(raw_lot_size / volume_step) * volume_step
                        if calculated_lots < volume_min:
                            calculated_lots = volume_min
                        elif calculated_lots > volume_max:
                            calculated_lots = volume_max
                        
                        step_decimals = len(str(volume_step).split('.')[1]) if '.' in str(volume_step) else 0
                        calculated_lots = round(calculated_lots, step_decimals)
                        mt5_adjusted = True
                conn.shutdown()
        except Exception as e:
            print(f"⚠️ Exception during pre-order volume adjustment check: {e}")

    if not mt5_adjusted:
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

    # Place MT5 Order
    mt5_status = place_mt5_order(
        symbol=pair_clean,
        order_type=order_direction,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        lots=calculated_lots
    )

    # Build clean Telegram markdown message
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
        f"-----------------------------\n"
        f"🖥️ *MT5 Order Status:*\n{mt5_status}\n"
        f"============================="
    )

    # Dispatch to device
    send_telegram_alert(tg_message)
