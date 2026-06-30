from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from burnrate.db.models import Category, CategorizationRule, Transaction


class RulesService:
    def __init__(self, *, db: Session) -> None:
        self.db = db

    def list_rules(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(CategorizationRule, Category.name)
            .join(Category, Category.id == CategorizationRule.category_id)
            .order_by(CategorizationRule.priority.asc(), CategorizationRule.created_at.asc())
        ).all()
        return [
            self._serialize_rule(rule=rule, category_name=category_name)
            for rule, category_name in rows
        ]

    def create_rule_from_transaction(
        self,
        *,
        transaction_id: str,
        name: str | None = None,
        match_field: str | None = None,
        match_operator: str = "contains",
        match_value: str | None = None,
        category_id: str | None = None,
        apply_to_existing_uncategorized: bool = False,
    ) -> dict[str, Any]:
        transaction = self.db.get(Transaction, self._parse_uuid(transaction_id, "Transaction id"))
        if transaction is None:
            raise ValueError(f"Transaction not found for id {transaction_id}")

        resolved_category = self._resolve_category(
            category_id=category_id,
            transaction=transaction,
        )
        resolved_match_field = match_field or self._suggest_match_field(transaction=transaction)
        field_value = self._transaction_field_value(transaction=transaction, field_name=resolved_match_field)
        if not field_value:
            raise ValueError(f"Transaction has no value for match field '{resolved_match_field}'")

        resolved_match_value = self._normalize_match_value(match_value or field_value)
        self._validate_operator_and_value(
            match_operator=match_operator,
            match_value=resolved_match_value,
        )

        duplicate = self.db.scalar(
            select(CategorizationRule).where(
                CategorizationRule.category_id == resolved_category.id,
                CategorizationRule.match_field == resolved_match_field,
                CategorizationRule.match_operator == match_operator,
                CategorizationRule.match_value == resolved_match_value,
            )
        )
        if duplicate is not None:
            raise ValueError("An identical categorization rule already exists")

        priority = (self.db.scalar(select(func.max(CategorizationRule.priority))) or 0) + 1
        rule = CategorizationRule(
            name=self._normalize_name(name) if name else self._default_rule_name(
                category_name=resolved_category.name,
                field_name=resolved_match_field,
                match_operator=match_operator,
                match_value=resolved_match_value,
            ),
            match_field=resolved_match_field,
            match_operator=match_operator,
            match_value=resolved_match_value,
            category_id=resolved_category.id,
            priority=priority,
            active=True,
            created_from_manual_classification=True,
        )
        self.db.add(rule)
        self.db.flush()

        transaction.category_id = resolved_category.id
        transaction.matched_rule_id = rule.id

        if apply_to_existing_uncategorized:
            self.apply_rule_to_existing_uncategorized(rule_id=str(rule.id))

        return self._serialize_rule(rule=rule, category_name=resolved_category.name)

    def set_rule_status(self, *, rule_id: str, active: bool) -> dict[str, Any]:
        rule = self.db.get(CategorizationRule, self._parse_uuid(rule_id, "Rule id"))
        if rule is None:
            raise ValueError(f"Rule not found for id {rule_id}")

        category = self.db.get(Category, rule.category_id)
        assert category is not None
        rule.active = active
        return self._serialize_rule(rule=rule, category_name=category.name)

    def update_rule(
        self,
        *,
        rule_id: str,
        name: str | None = None,
        match_field: str,
        match_operator: str,
        match_value: str,
        apply_to_existing_uncategorized: bool = False,
    ) -> dict[str, Any]:
        rule = self.db.get(CategorizationRule, self._parse_uuid(rule_id, "Rule id"))
        if rule is None:
            raise ValueError(f"Rule not found for id {rule_id}")

        category = self.db.get(Category, rule.category_id)
        assert category is not None

        resolved_match_value = self._normalize_match_value(match_value)
        self._validate_operator_and_value(
            match_operator=match_operator,
            match_value=resolved_match_value,
        )

        duplicate = self.db.scalar(
            select(CategorizationRule).where(
                CategorizationRule.id != rule.id,
                CategorizationRule.category_id == rule.category_id,
                CategorizationRule.match_field == match_field,
                CategorizationRule.match_operator == match_operator,
                CategorizationRule.match_value == resolved_match_value,
            )
        )
        if duplicate is not None:
            raise ValueError("An identical categorization rule already exists")

        self._validate_match_field(match_field)
        rule.match_field = match_field
        rule.match_operator = match_operator
        rule.match_value = resolved_match_value
        rule.name = (
            self._normalize_name(name)
            if name and name.strip()
            else self._default_rule_name(
                category_name=category.name,
                field_name=match_field,
                match_operator=match_operator,
                match_value=resolved_match_value,
            )
        )

        if apply_to_existing_uncategorized:
            self.apply_rule_to_existing_uncategorized(rule_id=str(rule.id))

        return self._serialize_rule(rule=rule, category_name=category.name)

    def apply_rule_to_transaction(self, *, transaction: Transaction) -> bool:
        if transaction.category_id is not None:
            return False

        rules = self.db.scalars(
            select(CategorizationRule)
            .where(CategorizationRule.active.is_(True))
            .order_by(CategorizationRule.priority.asc(), CategorizationRule.created_at.asc())
        ).all()

        for rule in rules:
            transaction_value = self._transaction_field_value(transaction=transaction, field_name=rule.match_field)
            if not transaction_value:
                continue
            if self._matches(
                source_value=transaction_value,
                match_operator=rule.match_operator,
                match_value=rule.match_value,
            ):
                transaction.category_id = rule.category_id
                transaction.matched_rule_id = rule.id
                return True

        return False

    def apply_rule_to_existing_uncategorized(self, *, rule_id: str) -> int:
        rule = self.db.get(CategorizationRule, self._parse_uuid(rule_id, "Rule id"))
        if rule is None:
            raise ValueError(f"Rule not found for id {rule_id}")

        transactions = self.db.scalars(
            select(Transaction).where(Transaction.category_id.is_(None)).order_by(Transaction.created_at.asc())
        ).all()

        applied = 0
        for transaction in transactions:
            transaction_value = self._transaction_field_value(transaction=transaction, field_name=rule.match_field)
            if not transaction_value:
                continue
            if self._matches(
                source_value=transaction_value,
                match_operator=rule.match_operator,
                match_value=rule.match_value,
            ):
                transaction.category_id = rule.category_id
                transaction.matched_rule_id = rule.id
                applied += 1

        return applied

    def _serialize_rule(self, *, rule: CategorizationRule, category_name: str) -> dict[str, Any]:
        return {
            "rule_id": str(rule.id),
            "name": rule.name,
            "match_field": rule.match_field,
            "match_operator": rule.match_operator,
            "match_value": rule.match_value,
            "category_id": str(rule.category_id),
            "category_name": category_name,
            "priority": rule.priority,
            "active": rule.active,
            "created_from_manual_classification": rule.created_from_manual_classification,
        }

    def _resolve_category(self, *, category_id: str | None, transaction: Transaction) -> Category:
        resolved_category_id = category_id
        if resolved_category_id is None:
            if transaction.category_id is None:
                raise ValueError("Transaction must already be categorized or provide category_id")
            resolved_category_id = str(transaction.category_id)

        category = self.db.get(Category, self._parse_uuid(resolved_category_id, "Category id"))
        if category is None:
            raise ValueError(f"Category not found for id {resolved_category_id}")
        if not category.active:
            raise ValueError(f"Category '{category.name}' is inactive")
        return category

    def _suggest_match_field(self, *, transaction: Transaction) -> str:
        for field_name in ("merchant_name", "description", "counterparty_name"):
            if self._transaction_field_value(transaction=transaction, field_name=field_name):
                return field_name
        raise ValueError("Transaction does not contain a usable text field for rule creation")

    def _transaction_field_value(self, *, transaction: Transaction, field_name: str) -> str | None:
        self._validate_match_field(field_name)
        value = getattr(transaction, field_name, None)
        if value is None:
            return None
        normalized = " ".join(str(value).split()).strip()
        return normalized or None

    def _matches(self, *, source_value: str, match_operator: str, match_value: str) -> bool:
        source = source_value.casefold()
        target = match_value.casefold()
        if match_operator == "contains":
            return target in source
        if match_operator == "equals":
            return source == target
        if match_operator == "starts_with":
            return source.startswith(target)
        if match_operator == "ends_with":
            return source.endswith(target)
        if match_operator == "regex":
            return re.search(match_value, source_value, re.IGNORECASE) is not None
        raise ValueError(f"Unsupported match operator '{match_operator}'")

    def _validate_operator_and_value(self, *, match_operator: str, match_value: str) -> None:
        if match_operator not in {"contains", "equals", "starts_with", "ends_with", "regex"}:
            raise ValueError(f"Unsupported match operator '{match_operator}'")
        if not match_value.strip():
            raise ValueError("Match value must not be empty")
        if match_operator == "regex":
            try:
                re.compile(match_value)
            except re.error as exc:
                raise ValueError(f"Invalid regex pattern: {exc}") from exc

    def _default_rule_name(
        self,
        *,
        category_name: str,
        field_name: str,
        match_operator: str,
        match_value: str,
    ) -> str:
        return f"{category_name} from {field_name} {match_operator} {match_value}"

    def _validate_match_field(self, field_name: str) -> None:
        if field_name not in {"description", "merchant_name", "counterparty_name"}:
            raise ValueError(f"Unsupported match field '{field_name}'")

    def _normalize_name(self, value: str) -> str:
        normalized = " ".join(value.split()).strip()
        if not normalized:
            raise ValueError("Rule name must not be empty")
        return normalized

    def _normalize_match_value(self, value: str) -> str:
        normalized = " ".join(value.split()).strip()
        if not normalized:
            raise ValueError("Match value must not be empty")
        return normalized

    def _parse_uuid(self, value: str, label: str) -> UUID:
        try:
            return UUID(value)
        except ValueError as exc:
            raise ValueError(f"{label} must be a valid UUID") from exc
