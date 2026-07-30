# Z-Score Mean Reversion Trading Bot with MetaTrader 5 Integration

An automated trading bot that calculates Statistical Mean Reversion signals using Z-Scores on currency pairs, manages trade risk parameters (position sizing, Stop Loss, Take Profit), and connects to **MetaTrader 5** to automatically place Limit Orders while broadcasting real-time execution alerts via a **Telegram Chatbot**.

---

## Key Features

1. **Indicator Analysis**:
   - Downloads live historical data from yfinance.
   - Calculates Rolling Mean, Rolling Standard Deviation, and Z-Scores.
   - Utilizes a 200-period Simple Moving Average (SMA 200) trend filter to ensure alignment with major market trends.
2. **Automated MT5 Execution**:
   - Integrates with the MetaTrader 5 Python library (`MetaTrader5`).
   - Automatically opens pending **Buy Limit** (for oversold mean reversions) and **Sell Limit** (for overbought mean reversions) orders.
   - Dynamically calculates Stop Loss (SL) and Take Profit (TP) levels.
   - Checks broker specifications (like digit counts and filling modes: FOK, IOC, or RETURN) to format prices and execution requests correctly.
3. **Telegram Chatbot Integration**:
   - Broadcasts detailed Markdown formatted trade notifications immediately upon signal detection.
   - Displays real-time MT5 execution status (successful ticket numbers, entry prices, SL/TP levels, or specific error/rejection details).

---

## Installation & Setup

This project supports running on both **Windows** (native `MetaTrader5`) and **Linux** (using `pymt5linux` under Wine in headless mode).

### 1. Install Dependencies

#### On Windows:
You can install dependencies using:
```bash
pip install numpy pandas requests yfinance MetaTrader5
```

#### On Linux (Option 1 - pymt5linux under Wine):
1. **Install Wine and Xvfb (Virtual Framebuffer for Headless running):**
   ```bash
   sudo apt update
   sudo apt install wine xvfb -y
   ```
2. **Install Python for Windows inside Wine:**
   ```bash
   wget https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe
   wine python-3.10.11-amd64.exe /quiet InstallAllUsers=1 PrependPath=1
   ```
3. **Install dependencies in Wine and native Linux:**
   ```bash
   # On Wine Python:
   wine python -m pip install MetaTrader5 pymt5linux

   # On Native Linux Python (or using 'uv sync'):
   pip install numpy pandas requests yfinance pymt5linux
   ```
4. **Launch MetaTrader 5 headlessly under Wine:**
   ```bash
   xvfb-run -a wine python -m pymt5linux
   ```
   *(This starts the RPC server on port `18812` which your native Linux Python code connects to).*

### 2. Configure credentials
Open [zscore.py](file:///home/kaungminkhant/z-score/zscore.py) and update the configurations in the header block:

```python
# ==========================================
# TELEGRAM CONFIGURATION
# ==========================================
TELEGRAM_BOT_TOKEN = "your_bot_token"
TELEGRAM_CHAT_ID = "your_chat_id"

# ==========================================
# METATRADER 5 CONFIGURATION
# ==========================================
MT5_LOGIN = None       # e.g., 12345678 (must be an integer)
MT5_PASSWORD = None    # e.g., "your_password" (string)
MT5_SERVER = None      # e.g., "Your-Broker-Server" (string)
MT5_PATH = None        # e.g., "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
```
*Note: If MetaTrader 5 is already logged in on the machine running the script, you can leave `MT5_LOGIN`, `MT5_PASSWORD`, and `MT5_SERVER` as `None`.*

---

## How it works

1. **Signals**:
   - **Buy Limit**: Triggered when `Z-Score <= -2.0` and price is above the 200 SMA.
   - **Sell Limit**: Triggered when `Z-Score >= 2.0` and price is below the 200 SMA.
2. **Order Price Logic**:
   - **Entry Price**: Set to the latest close price.
   - **Stop Loss (SL)**: Set at `Rolling Mean ± (3 * Rolling Std)`.
   - **Take Profit (TP)**: Set at the `Rolling Mean`.
3. **Volume Management**:
   - Accounts for account balance, custom risk percentage, JPY cross rates, standard pip calculations, and automatically adjusts lot sizes to match the broker's minimum/maximum lot steps if MT5 is initialized.

---

## Running the Bot

Run the analysis by executing:
```bash
python main.py
```
This triggers the logic for the analyzed currency pairs specified in [main.py](file:///home/kaungminkhant/z-score/main.py).
