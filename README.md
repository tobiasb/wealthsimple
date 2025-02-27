Script to interact with the Wealthsimple API to fetch basic account data. Works with OTP protected accounts.

```bash
pipenv run python app.py --username={wealthsimple_username} --start=2025-01-01T00:00:00.000000+08:00 --end=2026-01-01T00:00:00.000000+08:00
```

- Outputs a hash account types (TFSA/RRSP/etc) and the sum of their "liquidation values". Helpful when putting together info about ones "net worth".
- Outputs transactions in TFSA and RRSP accounts that can be copy/pasted onto a spreadsheet. Helpful when tracking contributions.
