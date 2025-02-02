Scripts to interact with the Wealthsimple API to fetch basic account data. Works with OTP protected accounts.

# Get Summary
```bash
pipenv run python app.py --username=tobiasboehm@fastmail.com --summary
```

Outputs a hash account types (TFSA/RRSP/etc) and the sum of their "liquidation values". Helpful when putting together info about ones "net worth".

# Get Transactions
```bash
pipenv run python app.py --username=tobiasboehm@fastmail.com --transactions --start=2024-01-01T00:00:00.000000+08:00 --end=2025-01-01T00:00:00.000000+08:00
```

List of RRSP/TFSA transactions that can be copy/pasted onto a spreadsheet. Helpful when tracking contributions.
