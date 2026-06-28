"""Initial BurnRate schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "enable_banking_app_configs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("app_id", sa.Text(), nullable=False),
        sa.Column("environment", sa.Text(), nullable=False),
        sa.Column("redirect_url", sa.Text(), nullable=False),
        sa.Column("restricted_mode", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("app_id", name="uq_enable_banking_app_configs_app_id"),
    )

    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("included_in_calculations", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("included_in_runway", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("latest_balance_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("latest_balance_currency", sa.Text(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_accounts_included_in_calculations", "accounts", ["included_in_calculations"])
    op.create_index("ix_accounts_included_in_runway", "accounts", ["included_in_runway"])

    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", name="uq_categories_name"),
    )

    op.create_table(
        "enable_banking_connections",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("aspsp_name", sa.Text(), nullable=False),
        sa.Column("aspsp_country", sa.Text(), nullable=False),
        sa.Column("psu_type", sa.Text(), nullable=False),
        sa.Column("session_id", sa.Text(), nullable=True),
        sa.Column("session_status", sa.Text(), nullable=True),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_enable_banking_connections_aspsp_country_name",
        "enable_banking_connections",
        ["aspsp_country", "aspsp_name"],
    )
    op.create_index("ix_enable_banking_connections_session_id", "enable_banking_connections", ["session_id"])

    op.create_table(
        "categorization_rules",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("match_field", sa.Text(), nullable=False),
        sa.Column("match_operator", sa.Text(), nullable=False),
        sa.Column("match_value", sa.Text(), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_from_manual_classification",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], name="fk_categorization_rules_category_id"),
    )
    op.create_index("ix_categorization_rules_active", "categorization_rules", ["active"])
    op.create_index("ix_categorization_rules_category_id", "categorization_rules", ["category_id"])
    op.create_index("ix_categorization_rules_priority", "categorization_rules", ["priority"])

    op.create_table(
        "budgets",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("period_type", sa.Text(), nullable=False),
        sa.Column("active_from", sa.Date(), nullable=False),
        sa.Column("active_to", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], name="fk_budgets_category_id"),
    )
    op.create_index("ix_budgets_active_from", "budgets", ["active_from"])
    op.create_index("ix_budgets_active_to", "budgets", ["active_to"])
    op.create_index("ix_budgets_category_id", "budgets", ["category_id"])

    op.create_table(
        "enable_banking_account_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("enable_banking_connection_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("external_account_id", sa.Text(), nullable=False),
        sa.Column("external_account_hash", sa.Text(), nullable=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_enable_banking_account_mappings_account_id",
        ),
        sa.ForeignKeyConstraint(
            ["enable_banking_connection_id"],
            ["enable_banking_connections.id"],
            name="fk_enable_banking_account_mappings_connection_id",
        ),
        sa.UniqueConstraint("external_account_id", name="uq_enable_banking_account_mappings_external_account_id"),
    )

    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("enable_banking_transaction_id", sa.Text(), nullable=True),
        sa.Column("booking_date", sa.Date(), nullable=True),
        sa.Column("value_date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("merchant_name", sa.Text(), nullable=True),
        sa.Column("counterparty_name", sa.Text(), nullable=True),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("matched_rule_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name="fk_transactions_account_id"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], name="fk_transactions_category_id"),
        sa.ForeignKeyConstraint(
            ["matched_rule_id"],
            ["categorization_rules.id"],
            name="fk_transactions_matched_rule_id",
        ),
        sa.UniqueConstraint(
            "enable_banking_transaction_id",
            name="uq_transactions_enable_banking_transaction_id",
        ),
    )
    op.create_index("ix_transactions_account_id", "transactions", ["account_id"])
    op.create_index("ix_transactions_account_id_booking_date", "transactions", ["account_id", "booking_date"])
    op.create_index("ix_transactions_booking_date", "transactions", ["booking_date"])
    op.create_index("ix_transactions_category_id", "transactions", ["category_id"])
    op.create_index("ix_transactions_status", "transactions", ["status"])

    op.create_table(
        "sync_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("enable_banking_connection_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("imported_accounts_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("imported_transactions_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["enable_banking_connection_id"],
            ["enable_banking_connections.id"],
            name="fk_sync_sessions_connection_id",
        ),
    )
    op.create_index("ix_sync_sessions_started_at", "sync_sessions", ["started_at"])
    op.create_index("ix_sync_sessions_status", "sync_sessions", ["status"])

    op.create_table(
        "enable_banking_auth_requests",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("enable_banking_connection_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("redirect_url", sa.Text(), nullable=False),
        sa.Column("aspsp_name", sa.Text(), nullable=False),
        sa.Column("aspsp_country", sa.Text(), nullable=False),
        sa.Column("psu_type", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["enable_banking_connection_id"],
            ["enable_banking_connections.id"],
            name="fk_enable_banking_auth_requests_connection_id",
        ),
        sa.UniqueConstraint("state", name="uq_enable_banking_auth_requests_state"),
    )


def downgrade() -> None:
    op.drop_table("enable_banking_auth_requests")
    op.drop_index("ix_sync_sessions_status", table_name="sync_sessions")
    op.drop_index("ix_sync_sessions_started_at", table_name="sync_sessions")
    op.drop_table("sync_sessions")
    op.drop_index("ix_transactions_status", table_name="transactions")
    op.drop_index("ix_transactions_category_id", table_name="transactions")
    op.drop_index("ix_transactions_booking_date", table_name="transactions")
    op.drop_index("ix_transactions_account_id_booking_date", table_name="transactions")
    op.drop_index("ix_transactions_account_id", table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("enable_banking_account_mappings")
    op.drop_index("ix_budgets_category_id", table_name="budgets")
    op.drop_index("ix_budgets_active_to", table_name="budgets")
    op.drop_index("ix_budgets_active_from", table_name="budgets")
    op.drop_table("budgets")
    op.drop_index("ix_categorization_rules_priority", table_name="categorization_rules")
    op.drop_index("ix_categorization_rules_category_id", table_name="categorization_rules")
    op.drop_index("ix_categorization_rules_active", table_name="categorization_rules")
    op.drop_table("categorization_rules")
    op.drop_index("ix_enable_banking_connections_session_id", table_name="enable_banking_connections")
    op.drop_index(
        "ix_enable_banking_connections_aspsp_country_name",
        table_name="enable_banking_connections",
    )
    op.drop_table("enable_banking_connections")
    op.drop_table("categories")
    op.drop_index("ix_accounts_included_in_runway", table_name="accounts")
    op.drop_index("ix_accounts_included_in_calculations", table_name="accounts")
    op.drop_table("accounts")
    op.drop_table("enable_banking_app_configs")

