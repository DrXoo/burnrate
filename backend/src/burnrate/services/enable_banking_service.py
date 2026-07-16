from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
import logging
from typing import Any
from uuid import UUID
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from burnrate.api.schemas.enable_banking import StartAuthorizationRequest
from burnrate.config import Settings
from burnrate.services.connection_expiry import as_utc, expiry_status
from burnrate.db.models import (
    Account,
    EnableBankingAccountMapping,
    EnableBankingAppConfig,
    EnableBankingAuthRequest,
    EnableBankingConnection,
    SyncSession,
    Transaction,
)
from burnrate.integrations.enable_banking.client import EnableBankingAPIError, EnableBankingClient
from burnrate.services.rules_service import RulesService

logger = logging.getLogger(__name__)

# Safety buffer subtracted from an ASPSP's maximum_consent_validity so the
# requested valid_until does not exceed "now + maximum_consent_validity" by the
# time Enable Banking evaluates it (they reject anything over the cap).
_CONSENT_VALIDITY_MARGIN = timedelta(minutes=5)


@dataclass
class ImportSummary:
    accounts_imported: int = 0
    transactions_imported: int = 0


class EnableBankingService:
    def __init__(self, *, db: Session, settings: Settings, client: EnableBankingClient) -> None:
        self.db = db
        self.settings = settings
        self.client = client

    def list_connections(self) -> list[dict[str, Any]]:
        """List the current connection for each bank link, newest first.

        A re-authorization creates a new connection row and retires the previous one
        (see ``_supersede_previous_connections``), but the retired rows stay for their
        sync history. Surfacing them would show one row per past reconnect, which
        reads as a duplicated bank/account even though the accounts themselves are
        deduplicated. Keep only the newest row per link, which is the one that is
        live — or, if it lapsed and was never replaced, the one to reconnect.
        """
        connections = self.db.scalars(
            select(EnableBankingConnection).order_by(EnableBankingConnection.created_at.desc())
        ).all()

        current: dict[tuple[str, str, str], EnableBankingConnection] = {}
        for connection in connections:
            # Same key as _supersede_previous_connections, so what is hidden here is
            # exactly what a reconnect retired.
            key = (connection.aspsp_name, connection.aspsp_country, connection.psu_type)
            current.setdefault(key, connection)

        return [self._serialize_connection_summary(connection) for connection in current.values()]

    def list_aspsps(self, *, country: str) -> list[dict[str, Any]]:
        return self.client.list_aspsps(country=country)

    def start_authorization(self, request: StartAuthorizationRequest) -> dict[str, Any]:
        self._upsert_app_config()

        state = str(uuid4())
        valid_until = self._resolve_valid_until(request)
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

    def _resolve_valid_until(self, request: StartAuthorizationRequest) -> datetime:
        now = datetime.now(UTC)
        requested = timedelta(days=request.access_valid_for_days)

        max_validity = self._max_consent_validity(request.aspsp_name, request.aspsp_country)
        if max_validity is not None:
            capped = max(max_validity - _CONSENT_VALIDITY_MARGIN, timedelta(0))
            if capped < requested:
                logger.info(
                    "Clamping consent validity for %s (%s) from %s to %s (bank maximum)",
                    request.aspsp_name,
                    request.aspsp_country.upper(),
                    requested,
                    capped,
                )
                requested = capped

        return now + requested

    def _max_consent_validity(self, aspsp_name: str, aspsp_country: str) -> timedelta | None:
        """Return the ASPSP's maximum_consent_validity as a timedelta, or None if unknown."""
        try:
            aspsps = self.client.list_aspsps(country=aspsp_country)
        except EnableBankingAPIError as exc:
            logger.warning(
                "Could not fetch ASPSP list to determine max consent validity for %s: %s",
                aspsp_name,
                exc,
            )
            return None

        country = aspsp_country.upper()
        for aspsp in aspsps:
            if aspsp.get("name") != aspsp_name:
                continue
            if (aspsp.get("country") or "").upper() != country:
                continue
            seconds = aspsp.get("maximum_consent_validity")
            if isinstance(seconds, (int, float)) and seconds > 0:
                return timedelta(seconds=seconds)
            return None
        return None

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
            # Consent expiry we requested at auth start, so we can warn before it lapses.
            expires_at=auth_request.expires_at,
            active=True,
        )
        self.db.add(connection)
        self.db.flush()

        # A fresh authorization for the same bank supersedes the prior one, so a
        # reconnect renews access instead of leaving a stale duplicate behind.
        self._supersede_previous_connections(connection)

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
            # Log the local connection id, never the bank session token.
            logger.info(
                "Starting Enable Banking import for connection %s (%s/%s)",
                connection.id,
                auth_request.aspsp_name,
                auth_request.aspsp_country,
            )
            summary = self._import_session_accounts(
                connection=connection,
                session_payload=session_payload,
            )
            sync_session.status = "success"
            sync_session.imported_accounts_count = summary.accounts_imported
            sync_session.imported_transactions_count = summary.transactions_imported
            sync_session.finished_at = datetime.now(UTC)
            connection.last_synced_at = datetime.now(UTC)
            logger.info(
                "Completed Enable Banking import for connection %s: accounts=%s transactions=%s",
                connection.id,
                summary.accounts_imported,
                summary.transactions_imported,
            )
        except Exception as exc:
            sync_session.status = "failed"
            sync_session.error_summary = str(exc)
            sync_session.finished_at = datetime.now(UTC)
            logger.exception("Enable Banking import failed for connection %s", connection.id)
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
            "session_status": connection.session_status or "AUTHORIZED",
            "accounts_returned": accounts_returned,
            "accounts_imported": summary.accounts_imported,
            "transactions_imported": summary.transactions_imported,
            "message": message,
        }

    def sync_connection(self, *, connection_id: str) -> dict[str, Any]:
        connection = self.db.get(EnableBankingConnection, UUID(connection_id))
        if connection is None:
            raise ValueError(f"Enable Banking connection not found for id {connection_id}")
        if not connection.active:
            raise ValueError(f"Enable Banking connection {connection_id} is inactive")
        if not connection.session_id:
            raise ValueError(f"Enable Banking connection {connection_id} has no session_id")

        session_data = self.client.get_session(session_id=connection.session_id)
        session_status = session_data.get("status", connection.session_status or "AUTHORIZED")
        connection.session_status = session_status

        if not self._is_session_authorized(session_status):
            return self._handle_expired_session(connection=connection, session_status=session_status)

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
            summary = self._resync_connection_accounts(connection=connection)
            sync_session.status = "success"
            sync_session.imported_accounts_count = summary.accounts_imported
            sync_session.imported_transactions_count = summary.transactions_imported
            sync_session.finished_at = datetime.now(UTC)
            connection.last_synced_at = datetime.now(UTC)
            logger.info(
                "Completed manual Enable Banking sync for connection %s: accounts=%s transactions=%s",
                connection_id,
                summary.accounts_imported,
                summary.transactions_imported,
            )
        except Exception as exc:
            sync_session.status = "failed"
            sync_session.error_summary = str(exc)
            sync_session.finished_at = datetime.now(UTC)
            logger.exception("Manual Enable Banking sync failed for connection %s", connection_id)
            raise

        return {
            "connection_id": str(connection.id),
            "sync_session_id": str(sync_session.id),
            "session_status": connection.session_status or "AUTHORIZED",
            "accounts_synced": summary.accounts_imported,
            "transactions_imported": summary.transactions_imported,
            "status": "success",
            "message": None if summary.accounts_imported > 0 else "No linked accounts found for this connection.",
        }

    def _is_session_authorized(self, session_status: str | None) -> bool:
        return (session_status or "").upper() == "AUTHORIZED"

    def _handle_expired_session(
        self,
        *,
        connection: EnableBankingConnection,
        session_status: str,
    ) -> dict[str, Any]:
        """Record an expired/revoked session and deactivate the connection.

        A session that is no longer authorized cannot be refreshed automatically;
        the owner must re-authorize the bank. Deactivating the connection stops the
        background worker from retrying a doomed sync on every scheduled tick.
        """
        connection.active = False
        error_summary = (
            f"Enable Banking session is no longer authorized (status={session_status}). "
            "The connection was deactivated and must be re-authorized."
        )
        sync_session = SyncSession(
            enable_banking_connection_id=connection.id,
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            status="skipped",
            imported_accounts_count=0,
            imported_transactions_count=0,
            error_summary=error_summary,
        )
        self.db.add(sync_session)
        self.db.flush()
        logger.warning(
            "Skipping Enable Banking sync for connection %s: session status=%s",
            connection.id,
            session_status,
        )

        return {
            "connection_id": str(connection.id),
            "sync_session_id": str(sync_session.id),
            "session_status": session_status,
            "accounts_synced": 0,
            "transactions_imported": 0,
            "status": "skipped",
            "message": "Bank session expired. Please reconnect this account to resume syncing.",
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
            logger.info("Importing Enable Banking account %s", account_uid)
            local_account = self._upsert_local_account(
                connection=connection,
                account_payload=account_payload,
            )
            summary.accounts_imported += 1

            balances_payload = self.client.get_account_balances(account_id=account_uid)
            self._apply_latest_balance(local_account=local_account, balances_payload=balances_payload)

            summary.transactions_imported += self._import_account_transactions(
                local_account=local_account,
                account_uid=account_uid,
            )

        return summary

    def _resync_connection_accounts(
        self,
        *,
        connection: EnableBankingConnection,
    ) -> ImportSummary:
        mappings = self.db.scalars(
            select(EnableBankingAccountMapping).where(
                EnableBankingAccountMapping.enable_banking_connection_id == connection.id
            )
        ).all()

        summary = ImportSummary()
        for mapping in mappings:
            local_account = self.db.get(Account, mapping.account_id)
            if local_account is None:
                logger.warning(
                    "Skipping Enable Banking mapping %s because local account %s no longer exists",
                    mapping.id,
                    mapping.account_id,
                )
                continue

            mapping.last_seen_at = datetime.now(UTC)
            local_account.last_synced_at = datetime.now(UTC)
            logger.info("Manual sync for Enable Banking account %s", mapping.external_account_id)
            summary.accounts_imported += 1

            balances_payload = self.client.get_account_balances(account_id=mapping.external_account_id)
            self._apply_latest_balance(local_account=local_account, balances_payload=balances_payload)

            summary.transactions_imported += self._import_account_transactions(
                local_account=local_account,
                account_uid=mapping.external_account_id,
            )

        return summary

    def _upsert_local_account(
        self,
        *,
        connection: EnableBankingConnection,
        account_payload: dict[str, Any],
    ) -> Account:
        uid = account_payload["uid"]
        identification_hash = account_payload.get("identification_hash")
        display_name = account_payload.get("name") or account_payload.get("details") or uid
        currency = account_payload.get("currency") or "EUR"
        now = datetime.now(UTC)

        # Fast path: this exact external account id is already mapped (a re-sync of
        # the same authorized session).
        mapping = self.db.scalar(
            select(EnableBankingAccountMapping).where(
                EnableBankingAccountMapping.external_account_id == uid
            )
        )

        # Reconnect path: Enable Banking issues a NEW per-session uid for the same
        # real account on each fresh authorization, so the uid lookup misses. Fall
        # back to the stable identification hash to recognize the account and reuse
        # its local row (and the user's inclusion setting) instead of duplicating it.
        if mapping is None and identification_hash:
            mapping = self.db.scalar(
                select(EnableBankingAccountMapping).where(
                    EnableBankingAccountMapping.external_account_hash == identification_hash
                )
            )

        if mapping:
            account = self.db.get(Account, mapping.account_id)
            assert account is not None
            account.display_name = display_name
            account.currency = currency
            account.last_synced_at = now
            # Move the mapping onto the current connection and uid so later syncs of
            # the freshly authorized connection resolve to this same account.
            mapping.enable_banking_connection_id = connection.id
            mapping.external_account_id = uid
            mapping.external_account_hash = identification_hash
            mapping.last_seen_at = now
            return account

        account = Account(
            display_name=display_name,
            currency=currency,
            included_in_calculations=True,
            last_synced_at=now,
        )
        self.db.add(account)
        self.db.flush()

        mapping = EnableBankingAccountMapping(
            enable_banking_connection_id=connection.id,
            external_account_id=uid,
            external_account_hash=identification_hash,
            account_id=account.id,
            last_seen_at=now,
        )
        self.db.add(mapping)
        self.db.flush()
        return account

    def _import_account_transactions(self, *, local_account: Account, account_uid: str) -> int:
        """Import booked and pending transactions for one external account.

        Booked transactions are fetched for the current month (the amounts that drive
        the budgets). Pending transactions are fetched separately with ``PDNG`` over a
        trailing window, because Enable Banking returns a single status per call and a held
        transaction may have originated in the previous month. Banks that do not expose
        pending transactions over open banking simply return nothing for the pending call.
        """
        booked_from, booked_to = self._current_month_transaction_window()
        imported = self._fetch_and_upsert_transactions(
            local_account=local_account,
            account_uid=account_uid,
            date_from=booked_from,
            date_to=booked_to,
            transaction_status=None,
        )
        pending_from, pending_to = self._pending_transaction_window()
        imported += self._fetch_and_upsert_transactions(
            local_account=local_account,
            account_uid=account_uid,
            date_from=pending_from,
            date_to=pending_to,
            transaction_status="PDNG",
        )
        return imported

    def _fetch_and_upsert_transactions(
        self,
        *,
        local_account: Account,
        account_uid: str,
        date_from: date,
        date_to: date,
        transaction_status: str | None,
    ) -> int:
        imported = 0
        continuation_key: str | None = None
        page_number = 1
        while True:
            transactions_payload = self.client.get_account_transactions(
                account_id=account_uid,
                date_from=date_from,
                date_to=date_to,
                transaction_status=transaction_status,
                continuation_key=continuation_key,
            )
            transactions = self._extract_transactions(transactions_payload)
            payload_summary = self._summarize_transactions_payload(transactions_payload)
            log_level = logging.INFO if transactions else logging.WARNING
            logger.log(
                log_level,
                "Fetched Enable Banking transactions for account %s status=%s page=%s window=%s..%s imported=%s summary=%s",
                account_uid,
                transaction_status or "BOOK",
                page_number,
                date_from.isoformat(),
                date_to.isoformat(),
                len(transactions),
                payload_summary,
            )
            # Count only genuinely-new rows: booked transactions are re-fetched for the
            # whole current month on every sync, so counting all fetched rows would
            # re-report the same transactions (and falsely trigger "N new" alerts).
            for transaction_payload in transactions:
                if self._upsert_transaction(
                    local_account=local_account,
                    transaction_payload=transaction_payload,
                ):
                    imported += 1
            continuation_key = transactions_payload.get("continuation_key")
            if not continuation_key:
                break
            page_number += 1
        return imported

    def _current_month_transaction_window(self) -> tuple[date, date]:
        today = datetime.now(UTC).date()
        return date(today.year, today.month, 1), today

    def _pending_transaction_window(self) -> tuple[date, date]:
        today = datetime.now(UTC).date()
        return today - timedelta(days=30), today

    def _supersede_previous_connections(self, connection: EnableBankingConnection) -> None:
        """Deactivate earlier connections to the same bank/account-type.

        Matching on aspsp + psu_type keeps a distinct personal vs. business link to
        the same bank independent, while a re-authorization of the same link retires
        the old row.
        """
        previous = self.db.scalars(
            select(EnableBankingConnection).where(
                EnableBankingConnection.id != connection.id,
                EnableBankingConnection.aspsp_name == connection.aspsp_name,
                EnableBankingConnection.aspsp_country == connection.aspsp_country,
                EnableBankingConnection.psu_type == connection.psu_type,
                EnableBankingConnection.active.is_(True),
            )
        ).all()
        for stale in previous:
            stale.active = False

    def _expiry_fields(self, connection: EnableBankingConnection) -> dict[str, Any]:
        status, days = expiry_status(
            connection.expires_at,
            now=datetime.now(UTC),
            warning_days=self.settings.connection_expiry_warning_days,
        )
        expires = as_utc(connection.expires_at)
        return {
            "expires_at": expires.isoformat() if expires else None,
            "days_until_expiry": days,
            "expiry_status": status,
        }

    def _serialize_connection_summary(
        self,
        connection: EnableBankingConnection,
    ) -> dict[str, Any]:
        linked_account_count = self.db.query(EnableBankingAccountMapping).filter(
            EnableBankingAccountMapping.enable_banking_connection_id == connection.id
        ).count()
        latest_sync = self.db.scalar(
            select(SyncSession)
            .where(SyncSession.enable_banking_connection_id == connection.id)
            .order_by(SyncSession.started_at.desc())
        )

        return {
            "connection_id": str(connection.id),
            "aspsp_name": connection.aspsp_name,
            "aspsp_country": connection.aspsp_country,
            "psu_type": connection.psu_type,
            "session_status": connection.session_status,
            "active": connection.active,
            "authorized_at": connection.authorized_at.isoformat() if connection.authorized_at else None,
            "last_synced_at": connection.last_synced_at.isoformat() if connection.last_synced_at else None,
            **self._expiry_fields(connection),
            "linked_account_count": linked_account_count,
            "latest_sync_status": latest_sync.status if latest_sync else None,
            "latest_sync_started_at": latest_sync.started_at.isoformat() if latest_sync else None,
            "latest_sync_finished_at": latest_sync.finished_at.isoformat() if latest_sync and latest_sync.finished_at else None,
            "latest_sync_accounts_count": latest_sync.imported_accounts_count if latest_sync else None,
            "latest_sync_transactions_count": latest_sync.imported_transactions_count if latest_sync else None,
            "latest_sync_error_summary": latest_sync.error_summary if latest_sync else None,
        }

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

    def _upsert_transaction(self, *, local_account: Account, transaction_payload: dict[str, Any]) -> bool:
        """Insert or update one transaction. Returns True only when a new row was created."""
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
        creditor = transaction_payload.get("creditor") or {}
        debtor = transaction_payload.get("debtor") or {}
        merchant_name = creditor.get("name")
        counterparty_name = debtor.get("name")

        created = transaction is None
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

        RulesService(db=self.db).apply_rule_to_transaction(transaction=transaction)
        return created

    def _extract_transactions(self, transactions_payload: dict[str, Any]) -> list[dict[str, Any]]:
        transactions_node = transactions_payload.get("transactions")
        if isinstance(transactions_node, list):
            return transactions_node

        if isinstance(transactions_node, dict):
            booked = transactions_node.get("booked") or []
            pending = transactions_node.get("pending") or []
            return [*booked, *pending]

        booked = transactions_payload.get("booked") or []
        pending = transactions_payload.get("pending") or []
        return [*booked, *pending]

    def _summarize_transactions_payload(self, transactions_payload: dict[str, Any]) -> dict[str, Any]:
        transactions_node = transactions_payload.get("transactions")
        booked: list[dict[str, Any]] = []
        pending: list[dict[str, Any]] = []

        if isinstance(transactions_node, dict):
            booked = transactions_node.get("booked") or []
            pending = transactions_node.get("pending") or []
        else:
            booked = transactions_payload.get("booked") or []
            pending = transactions_payload.get("pending") or []

        return {
            "keys": sorted(transactions_payload.keys()),
            "transactions_type": type(transactions_node).__name__ if transactions_node is not None else None,
            "transactions_count": len(transactions_node) if isinstance(transactions_node, list) else 0,
            "booked_count": len(booked),
            "pending_count": len(pending),
            "continuation_key_present": bool(transactions_payload.get("continuation_key")),
        }

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
