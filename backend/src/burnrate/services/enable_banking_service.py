from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from burnrate.api.schemas.enable_banking import StartAuthorizationRequest
from burnrate.config import Settings
from burnrate.db.models import (
    Account,
    EnableBankingAccountMapping,
    EnableBankingAppConfig,
    EnableBankingAuthRequest,
    EnableBankingConnection,
    SyncSession,
    Transaction,
)
from burnrate.integrations.enable_banking.client import EnableBankingClient


@dataclass
class ImportSummary:
    accounts_imported: int = 0
    transactions_imported: int = 0


class EnableBankingService:
    def __init__(self, *, db: Session, settings: Settings, client: EnableBankingClient) -> None:
        self.db = db
        self.settings = settings
        self.client = client

    def list_aspsps(self, *, country: str) -> list[dict[str, Any]]:
        return self.client.list_aspsps(country=country)

    def start_authorization(self, request: StartAuthorizationRequest) -> dict[str, Any]:
        self._upsert_app_config()

        state = str(uuid4())
        valid_until = datetime.now(UTC) + timedelta(days=request.access_valid_for_days)
        response = self.client.start_authorization(
            aspsp_name=request.aspsp_name,
            aspsp_country=request.aspsp_country,
            state=state,
            redirect_url=self.settings.enable_banking_redirect_url,
            psu_type=request.psu_type,
            valid_until=valid_until,
        )

        auth_request = EnableBankingAuthRequest(
            state=state,
            redirect_url=self.settings.enable_banking_redirect_url,
            aspsp_name=request.aspsp_name,
            aspsp_country=request.aspsp_country.upper(),
            psu_type=request.psu_type,
            expires_at=valid_until,
        )
        self.db.add(auth_request)
        self.db.flush()

        return {
            "authorization_id": response.get("authorization_id"),
            "psu_id_hash": response.get("psu_id_hash"),
            "state": state,
            "url": response["url"],
            "valid_until": valid_until.isoformat(),
        }

    def handle_callback(
        self,
        *,
        code: str | None,
        state: str,
        error: str | None,
        error_description: str | None,
    ) -> dict[str, Any]:
        auth_request = self._get_auth_request(state=state)
        auth_request.completed_at = datetime.now(UTC)

        if error:
            raise ValueError(error_description or error)
        if not code:
            raise ValueError("Missing authorization code")

        session_payload = self.client.create_session(code=code)
        session_id = session_payload.get("session_id")
        if not session_id:
            raise ValueError("Enable Banking did not return a session_id")

        session_data = self.client.get_session(session_id=session_id)

        connection = EnableBankingConnection(
            aspsp_name=auth_request.aspsp_name,
            aspsp_country=auth_request.aspsp_country,
            psu_type=auth_request.psu_type,
            session_id=session_id,
            session_status=session_data.get("status", "AUTHORIZED"),
            authorized_at=self._parse_datetime(session_data.get("authorized")) or datetime.now(UTC),
            last_synced_at=datetime.now(UTC),
            active=True,
        )
        self.db.add(connection)
        self.db.flush()

        auth_request.enable_banking_connection_id = connection.id

        sync_session = SyncSession(
            enable_banking_connection_id=connection.id,
            started_at=datetime.now(UTC),
            status="running",
            imported_accounts_count=0,
            imported_transactions_count=0,
        )
        self.db.add(sync_session)
        self.db.flush()

        try:
            summary = self._import_session_accounts(
                connection=connection,
                session_payload=session_payload,
            )
            sync_session.status = "success"
            sync_session.imported_accounts_count = summary.accounts_imported
            sync_session.imported_transactions_count = summary.transactions_imported
            sync_session.finished_at = datetime.now(UTC)
            connection.last_synced_at = datetime.now(UTC)
        except Exception as exc:
            sync_session.status = "failed"
            sync_session.error_summary = str(exc)
            sync_session.finished_at = datetime.now(UTC)
            raise

        accounts_returned = len(session_payload.get("accounts", []))
        message = None
        if accounts_returned == 0:
            message = (
                "Authorization succeeded but no linked accounts were returned by Enable Banking. "
                "This can happen in restricted production mode when the authorized account is not "
                "linked to the current application."
            )

        return {
            "connection_id": str(connection.id),
            "session_id": session_id,
            "session_status": connection.session_status or "AUTHORIZED",
            "accounts_returned": accounts_returned,
            "accounts_imported": summary.accounts_imported,
            "transactions_imported": summary.transactions_imported,
            "message": message,
        }

    def _import_session_accounts(
        self,
        *,
        connection: EnableBankingConnection,
        session_payload: dict[str, Any],
    ) -> ImportSummary:
        summary = ImportSummary()
        for account_payload in session_payload.get("accounts", []):
            account_uid = account_payload["uid"]
            local_account = self._upsert_local_account(
                connection=connection,
                account_payload=account_payload,
            )
            summary.accounts_imported += 1

            balances_payload = self.client.get_account_balances(account_id=account_uid)
            self._apply_latest_balance(local_account=local_account, balances_payload=balances_payload)

            continuation_key: str | None = None
            while True:
                transactions_payload = self.client.get_account_transactions(
                    account_id=account_uid,
                    continuation_key=continuation_key,
                )
                transactions = transactions_payload.get("transactions", [])
                for transaction_payload in transactions:
                    self._upsert_transaction(
                        local_account=local_account,
                        transaction_payload=transaction_payload,
                    )
                summary.transactions_imported += len(transactions)
                continuation_key = transactions_payload.get("continuation_key")
                if not continuation_key:
                    break

        return summary

    def _upsert_local_account(
        self,
        *,
        connection: EnableBankingConnection,
        account_payload: dict[str, Any],
    ) -> Account:
        mapping = self.db.scalar(
            select(EnableBankingAccountMapping).where(
                EnableBankingAccountMapping.external_account_id == account_payload["uid"]
            )
        )

        display_name = account_payload.get("name") or account_payload.get("details") or account_payload["uid"]
        currency = account_payload.get("currency") or "EUR"
        now = datetime.now(UTC)

        if mapping:
            account = self.db.get(Account, mapping.account_id)
            assert account is not None
            account.display_name = display_name
            account.currency = currency
            account.last_synced_at = now
            mapping.last_seen_at = now
            mapping.external_account_hash = account_payload.get("identification_hash")
            return account

        account = Account(
            display_name=display_name,
            currency=currency,
            included_in_calculations=True,
            included_in_runway=False,
            last_synced_at=now,
        )
        self.db.add(account)
        self.db.flush()

        mapping = EnableBankingAccountMapping(
            enable_banking_connection_id=connection.id,
            external_account_id=account_payload["uid"],
            external_account_hash=account_payload.get("identification_hash"),
            account_id=account.id,
            last_seen_at=now,
        )
        self.db.add(mapping)
        self.db.flush()
        return account

    def _apply_latest_balance(self, *, local_account: Account, balances_payload: dict[str, Any]) -> None:
        selected_balance = None
        for balance in balances_payload.get("balances", []):
            if balance.get("balance_type") == "CLAV":
                selected_balance = balance
                break
        if not selected_balance:
            balances = balances_payload.get("balances", [])
            selected_balance = balances[0] if balances else None
        if not selected_balance:
            return

        balance_amount = selected_balance.get("balance_amount", {})
        amount = balance_amount.get("amount")
        currency = balance_amount.get("currency")
        if amount is not None:
            local_account.latest_balance_amount = Decimal(str(amount))
        if currency:
            local_account.latest_balance_currency = currency

    def _upsert_transaction(self, *, local_account: Account, transaction_payload: dict[str, Any]) -> None:
        external_id = self._transaction_external_id(local_account.id, transaction_payload)
        transaction = self.db.scalar(
            select(Transaction).where(Transaction.enable_banking_transaction_id == external_id)
        )

        amount_info = transaction_payload.get("transaction_amount") or {}
        amount = Decimal(str(amount_info.get("amount", "0")))
        direction_indicator = transaction_payload.get("credit_debit_indicator", "CRDT")
        if direction_indicator == "DBIT":
            amount = -abs(amount)
            direction = "debit"
        else:
            direction = "credit"

        status = self._normalize_transaction_status(transaction_payload.get("status"))
        description = self._build_transaction_description(transaction_payload)
        merchant_name = transaction_payload.get("creditor", {}).get("name")
        counterparty_name = transaction_payload.get("debtor", {}).get("name")

        if transaction is None:
            transaction = Transaction(
                account_id=local_account.id,
                enable_banking_transaction_id=external_id,
                imported_at=datetime.now(UTC),
            )
            self.db.add(transaction)

        transaction.booking_date = self._parse_date(transaction_payload.get("booking_date"))
        transaction.value_date = self._parse_date(transaction_payload.get("value_date"))
        transaction.amount = amount
        transaction.currency = amount_info.get("currency") or local_account.currency
        transaction.description = description
        transaction.merchant_name = merchant_name
        transaction.counterparty_name = counterparty_name
        transaction.direction = direction
        transaction.status = status
        transaction.raw_payload = transaction_payload

    def _transaction_external_id(self, account_id: str, transaction_payload: dict[str, Any]) -> str:
        explicit_id = transaction_payload.get("transaction_id") or transaction_payload.get("entry_reference")
        if explicit_id:
            return explicit_id

        stable_input = "|".join(
            [
                str(account_id),
                str(transaction_payload.get("booking_date", "")),
                str(transaction_payload.get("value_date", "")),
                str(transaction_payload.get("credit_debit_indicator", "")),
                str(transaction_payload.get("transaction_amount", {}).get("amount", "")),
                str(transaction_payload.get("transaction_amount", {}).get("currency", "")),
                " ".join(transaction_payload.get("remittance_information", []) or []),
            ]
        )
        return sha256(stable_input.encode("utf-8")).hexdigest()

    def _build_transaction_description(self, transaction_payload: dict[str, Any]) -> str | None:
        remittance = transaction_payload.get("remittance_information") or []
        if remittance:
            return " | ".join(remittance)
        return transaction_payload.get("note") or transaction_payload.get("reference_number")

    def _normalize_transaction_status(self, provider_status: str | None) -> str:
        mapping = {
            "BOOK": "booked",
            "PDNG": "pending",
            "CNCL": "ignored",
            "RJCT": "ignored",
            "SCHD": "pending",
        }
        return mapping.get(provider_status or "", "booked")

    def _upsert_app_config(self) -> None:
        config = self.db.scalar(select(EnableBankingAppConfig))
        if config is None:
            config = EnableBankingAppConfig(
                app_id=self.settings.enable_banking_app_id,
                environment=self.settings.enable_banking_environment,
                redirect_url=self.settings.enable_banking_redirect_url,
                restricted_mode=True,
            )
            self.db.add(config)
            self.db.flush()
            return

        config.app_id = self.settings.enable_banking_app_id
        config.environment = self.settings.enable_banking_environment
        config.redirect_url = self.settings.enable_banking_redirect_url
        config.restricted_mode = True

    def _get_auth_request(self, *, state: str) -> EnableBankingAuthRequest:
        auth_request = self.db.scalar(
            select(EnableBankingAuthRequest).where(EnableBankingAuthRequest.state == state)
        )
        if auth_request is None:
            raise ValueError(f"Authorization request not found for state {state}")
        return auth_request

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def _parse_date(self, value: str | None):
        if not value:
            return None
        return datetime.fromisoformat(f"{value}T00:00:00+00:00").date()
