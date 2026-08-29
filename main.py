import zscore
from datetime import datetime

# Optimal watchlist for a $200 account balance
WATCHLIST = ["EURUSD=X", "AUDUSD=X", "USDCAD=X", "NZDUSD=X"]

# Risk & Execution Configurations
ACCOUNT_BALANCE = 200.00
RISK_PCT = 0.02          # 2% cash risk per trade ($4.00)
MAX_LEVERAGE = 10.0      # Max 10:1 leverage ceiling (0.02 lots max on $200 account)
MIN_STOP_PIPS = 18.0     # Minimum Stop Loss buffer in pips (eliminates spread noise stop-outs)
MAX_ADX = 25.0           # ADX regime threshold (< 25 = Ranging, >= 25 = Trending Block)


def main():
    print(
        "Starting quantitative mean reversion analysis for watchlist at:",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    # Iterate through target pairs
    for ticker in WATCHLIST:
        zscore.analyze_mean_reversion(
            ticker=ticker,
            account_balance=ACCOUNT_BALANCE,
            risk_pct=RISK_PCT,
            lookback=20,
            interval="1h",
            max_leverage=MAX_LEVERAGE,
            min_stop_pips=MIN_STOP_PIPS,
            max_adx=MAX_ADX,
            use_reversal_hook=True,
        )


if __name__ == "__main__":
    main()

