import argparse
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from getpass import getpass

import requests
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport

logging.basicConfig(level=logging.INFO)
logging.getLogger("gql.transport.aiohttp").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def obtain_access_token(username, password, otp=None):
    otp_header = {} if not otp else {"x-wealthsimple-otp": otp}

    response = requests.post(
        "https://api.production.wealthsimple.com/v1/oauth/v2/token",
        data={
            "grant_type": "password",
            "username": username,
            "password": password,
            "skip_provision": True,
            "otp_claim": None,
            "scope": "invest.read",
            "client_id": "4da53ac2b03225bed1550eba8e4611e086c7b905a3855e6ed12ea08c246758fa",
        },
        headers={
            **otp_header,
        },
    )
    response.raise_for_status()
    return response.json()["access_token"]


def get_identity(access_token):
    response = requests.get(
        "https://api.production.wealthsimple.com/v1/oauth/v2/token/info",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    token_info = response.json()
    return token_info["identity_canonical_id"], token_info["email"]


def get_account_type(account_id, account_owners):
    if account_id.startswith("rrsp"):
        return "rrsp"
    if account_id.startswith("group-rrsp"):
        return "rrsp"
    if account_id.startswith("tfsa"):
        return "tfsa"
    if account_id.startswith("non-registered"):
        return "non-registered"
    if account_id.startswith("ca-cash") and len(account_owners) > 1:
        return "cash-joint"
    if account_id.startswith("ca-cash"):
        return "cash"
    if account_id.startswith("resp"):
        return "resp-joint"
    return "unknown"


def get_summary(access_token, user_identity):
    transport = AIOHTTPTransport(
        url="https://my.wealthsimple.com/graphql",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    client = Client(transport=transport)

    with open("get-accounts.graphql", "r") as f:
        query = gql(f.read())

    accounts_info = client.execute(query, variable_values={"identityId": user_identity})

    totals = {}
    for node in accounts_info["identity"]["accounts"]["edges"]:
        account_info = node["node"]
        if account_info["status"] == "closed":
            continue
        if account_info["currency"] != "CAD":
            continue
        value = (
            account_info["financials"]["currentCombined"]
            .get("netLiquidationValueV2", {})
            .get("cents", None)
        )
        if not value:
            continue

        account_id = account_info["id"]
        account_type = get_account_type(account_id, account_info["accountOwners"])
        totals[account_type] = totals.get(account_type, 0) + (value / 100)

        print(
            f"{account_id}, {account_type}, {account_info['nickname']}, {value / 100 if value else None}"
        )
    return totals


def get_account_ids_by_type(access_token, user_identity, account_type):
    transport = AIOHTTPTransport(
        url="https://my.wealthsimple.com/graphql",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    client = Client(transport=transport)

    with open("get-accounts.graphql", "r") as f:
        query = gql(f.read())

    accounts_info = client.execute(query, variable_values={"identityId": user_identity})

    account_ids = []
    for node in accounts_info["identity"]["accounts"]["edges"]:
        account_id = node["node"]["id"]
        account_nickname = node["node"]["nickname"]

        if get_account_type(account_id, node["node"]["accountOwners"]) == account_type:
            account_ids.append(account_id)
            logger.debug(
                f"Adding account {account_id} ({account_nickname}) as it is of type {account_type}"
            )
        else:
            logger.debug(
                f"Skipping account {account_id} ({account_nickname}) as it is not of type {account_type}"
            )
    return account_ids


def get_transactions(access_token, user_identity, type, start, end):
    transport = AIOHTTPTransport(
        url="https://my.wealthsimple.com/graphql",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    client = Client(transport=transport)

    with open("get-transactions.graphql", "r") as f:
        query = gql(f.read())

    transactions = client.execute(
        query,
        variable_values={
            "first": 10000,
            "orderBy": "OCCURRED_AT_ASC",
            "condition": {
                "types": [
                    "INTERNAL_TRANSFER",
                    "INSTITUTIONAL_TRANSFER_INTENT",
                    "LEGACY_INTERNAL_TRANSFER",
                    "LEGACY_TRANSFER",
                    "CRYPTO_TRANSFER",
                    "DEPOSIT",
                ],
                "accountIds": get_account_ids_by_type(
                    access_token, user_identity, type
                ),
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
            },
        },
    )

    total = 0
    lines = []
    for node in transactions["activityFeedItems"]["edges"]:
        transaction = node["node"]
        amount = Decimal(transaction["amount"])
        timestamp = datetime.fromisoformat(transaction["occurredAt"])
        date = timestamp.strftime("%Y-%m-%d")
        
        if type == "rrsp":
            if timestamp.month <= 2:
                attribution = f"{timestamp.year - 1}-2"
            else:
                attribution = f"{timestamp.year}-1"
        else:
            attribution = f"{timestamp.year}"

        line = f"{date},{attribution},{amount},{transaction['opposingAccountId']},{transaction['accountId']}"

        total += amount
        lines.append(line)

    return lines, total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", type=str)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--transactions", action="store_true")
    parser.add_argument(
        f"--start", type=str, default=(datetime.now() - timedelta(days=30)).isoformat()
    )
    parser.add_argument(f"--end", type=str, default=datetime.now().isoformat())
    args = parser.parse_args()

    if not args.summary and not args.transactions:
        print("Please provide a command")
        return

    access_token = obtain_access_token(
        args.username, getpass("Enter password: "), input("Enter OTP: ")
    )

    user_identity, user_email = get_identity(access_token)
    print(f"User: {user_email}, Identity: {user_identity}")

    if args.summary:
        totals = get_summary(access_token, user_identity)
        print(json.dumps(totals, indent=2))
    if args.transactions:
        for account_type in ["rrsp", "tfsa"]:
            print(
                f"Transactions for {account_type.upper()} from {args.start} to {args.end}"
            )
            transactions, total = get_transactions(
                access_token,
                user_identity,
                account_type.lower(),
                datetime.fromisoformat(args.start),
                datetime.fromisoformat(args.end),
            )
            for line in transactions:
                print(line)
            print(f"Total: {total}")


if __name__ == "__main__":
    main()
