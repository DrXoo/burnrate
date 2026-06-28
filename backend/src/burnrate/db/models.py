from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from burnrate.db.base import Base, TimestampedMixin, UUIDPrimaryKeyMixin


class EnableBankingAppConfig(UUIDPrimaryKeyMixin, TimestampedMixin, Base):
    __tablename__ = "enable_banking_app_configs"

    app_id: Mapped[str] = mapped_column(Text, unique=True)
    environment: Mapped[str] = mapped_column(Text)
    redirect_url: Mapped[str] = mapped_column(Text)
    restricted_mode: Mapped[bool] = mapped_column(Boolean, default=True)


class Account(UUIDPrimaryKeyMixin, TimestampedMixin, Base):
    __tablename__ = "accounts"

    display_name: Mapped[str] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(Text)
    included_in_calculations: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    included_in_runway: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    latest_balance_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    latest_balance_currency: Mapped[str | None] = mapped_column(Text)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="account")


class Category(UUIDPrimaryKeyMixin, TimestampedMixin, Base):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(Text, unique=True)
    type: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class EnableBankingConnection(UUIDPrimaryKeyMixin, TimestampedMixin, Base):
    __tablename__ = "enable_banking_connections"

    aspsp_name: Mapped[str] = mapped_column(Text)
    aspsp_country: Mapped[str] = mapped_column(Text)
    psu_type: Mapped[str] = mapped_column(Text)
    session_id: Mapped[str | None] = mapped_column(Text, index=True)
    session_status: Mapped[str | None] = mapped_column(Text)
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class CategorizationRule(UUIDPrimaryKeyMixin, TimestampedMixin, Base):
    __tablename__ = "categorization_rules"

    name: Mapped[str | None] = mapped_column(Text)
    match_field: Mapped[str] = mapped_column(Text)
    match_operator: Mapped[str] = mapped_column(Text)
    match_value: Mapped[str] = mapped_column(Text)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"), index=True)
    priority: Mapped[int] = mapped_column(Integer, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_from_manual_classification: Mapped[bool] = mapped_column(Boolean, default=False)


class Budget(UUIDPrimaryKeyMixin, TimestampedMixin, Base):
    __tablename__ = "budgets"

    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(Text)
    period_type: Mapped[str] = mapped_column(Text)
    active_from: Mapped[date] = mapped_column(Date, index=True)
    active_to: Mapped[date | None] = mapped_column(Date, index=True)


class EnableBankingAccountMapping(UUIDPrimaryKeyMixin, TimestampedMixin, Base):
    __tablename__ = "enable_banking_account_mappings"

    enable_banking_connection_id: Mapped[str] = mapped_column(
        ForeignKey("enable_banking_connections.id")
    )
    external_account_id: Mapped[str] = mapped_column(Text, unique=True)
    external_account_hash: Mapped[str | None] = mapped_column(Text)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Transaction(UUIDPrimaryKeyMixin, TimestampedMixin, Base):
    __tablename__ = "transactions"

    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    enable_banking_transaction_id: Mapped[str | None] = mapped_column(Text, unique=True)
    booking_date: Mapped[date | None] = mapped_column(Date, index=True)
    value_date: Mapped[date | None] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    merchant_name: Mapped[str | None] = mapped_column(Text)
    counterparty_name: Mapped[str | None] = mapped_column(Text)
    direction: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, index=True)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id"), index=True)
    matched_rule_id: Mapped[str | None] = mapped_column(ForeignKey("categorization_rules.id"))
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    account: Mapped[Account] = relationship(back_populates="transactions")


class SyncSession(UUIDPrimaryKeyMixin, TimestampedMixin, Base):
    __tablename__ = "sync_sessions"

    enable_banking_connection_id: Mapped[str | None] = mapped_column(
        ForeignKey("enable_banking_connections.id")
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, index=True)
    imported_accounts_count: Mapped[int] = mapped_column(Integer, default=0)
    imported_transactions_count: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)


class EnableBankingAuthRequest(UUIDPrimaryKeyMixin, TimestampedMixin, Base):
    __tablename__ = "enable_banking_auth_requests"

    enable_banking_connection_id: Mapped[str | None] = mapped_column(
        ForeignKey("enable_banking_connections.id")
    )
    state: Mapped[str] = mapped_column(Text, unique=True)
    redirect_url: Mapped[str] = mapped_column(Text)
    aspsp_name: Mapped[str] = mapped_column(Text)
    aspsp_country: Mapped[str] = mapped_column(Text)
    psu_type: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

