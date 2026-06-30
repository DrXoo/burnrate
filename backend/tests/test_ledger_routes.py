from __future__ import annotations

from burnrate.api.routes.ledger import get_uncategorized_transaction_count, list_accounts, list_transactions
from burnrate.main import create_app


class FakeLedgerService:
    def list_accounts(self):
        return [
            {
                "account_id": "acc-1",
                "display_name": "Main account",
                "currency": "EUR",
                "latest_balance_amount": "375.52",
                "latest_balance_currency": "EUR",
                "included_in_calculations": True,
                "included_in_runway": False,
                "last_synced_at": "2026-06-29T08:05:00+00:00",
                "source_connection_id": "conn-1",
                "source_aspsp_name": "ING",
                "source_aspsp_country": "ES",
                "external_account_id": "ext-1",
            }
        ]

    def list_transactions(self, **_: object):
        return {
            "transactions": [
                {
                    "transaction_id": "tx-1",
                    "account_id": "acc-1",
                    "account_display_name": "Main account",
                    "booking_date": "2026-06-15",
                    "value_date": "2026-06-15",
                    "amount": "-12.50",
                    "currency": "EUR",
                    "description": "Coffee shop",
                    "merchant_name": "Cafe",
                    "counterparty_name": None,
                    "direction": "debit",
                    "status": "booked",
                    "category_id": None,
                    "category_name": None,
                    "matched_rule_id": None,
                    "matched_rule_name": None,
                    "imported_at": "2026-06-15T09:00:00+00:00",
                }
            ],
            "total_count": 1,
            "limit": 100,
            "offset": 0,
        }

    def get_uncategorized_transaction_count(self, **_: object):
        return 1


def test_ledger_routes_use_service_dependency() -> None:
    service = FakeLedgerService()

    accounts_response = list_accounts(service=service)
    transactions_response = list_transactions(
        account_id=None,
        month="2026-06",
        status_filter="booked",
        categorized=False,
        limit=100,
        offset=0,
        service=service,
    )
    uncategorized_response = get_uncategorized_transaction_count(
        account_id=None,
        month="2026-06",
        status_filter="booked",
        service=service,
    )

    assert accounts_response.accounts[0].display_name == "Main account"
    assert transactions_response.transactions[0].description == "Coffee shop"
    assert uncategorized_response.count == 1


def test_app_exposes_phase_3_ledger_paths() -> None:
    app = create_app()
    paths = set(app.openapi()["paths"].keys())

    assert "/api/v1/accounts" in paths
    assert "/api/v1/transactions" in paths
    assert "/api/v1/transactions/uncategorized/count" in paths
