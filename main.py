import zscore


def main():
    zscore.analyze_mean_reversion(
        "EURUSD=X", account_balance=200.00, risk_pct=0.02, lookback=20
    )
    zscore.analyze_mean_reversion(
        "GBPUSD=X", account_balance=200.00, risk_pct=0.02, lookback=20
    )
    zscore.analyze_mean_reversion(
        "AUDUSD=X", account_balance=200.00, risk_pct=0.02, lookback=20
    )


if __name__ == "__main__":
    main()
