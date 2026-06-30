from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from burnrate.config import Settings, get_settings
from burnrate.db.session import get_db
from burnrate.integrations.enable_banking.client import EnableBankingClient
from burnrate.services.budget_service import BudgetService
from burnrate.services.categorization_service import CategorizationService
from burnrate.services.enable_banking_service import EnableBankingService
from burnrate.services.ledger_service import LedgerService
from burnrate.services.rules_service import RulesService
from burnrate.services.summary_service import SummaryService


def get_enable_banking_client(
    settings: Settings = Depends(get_settings),
) -> EnableBankingClient:
    return EnableBankingClient(settings=settings)


def get_enable_banking_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    client: EnableBankingClient = Depends(get_enable_banking_client),
) -> EnableBankingService:
    return EnableBankingService(db=db, settings=settings, client=client)


def get_ledger_service(
    db: Session = Depends(get_db),
) -> LedgerService:
    return LedgerService(db=db)


def get_categorization_service(
    db: Session = Depends(get_db),
) -> CategorizationService:
    return CategorizationService(db=db)


def get_rules_service(
    db: Session = Depends(get_db),
) -> RulesService:
    return RulesService(db=db)


def get_budget_service(
    db: Session = Depends(get_db),
) -> BudgetService:
    return BudgetService(db=db)


def get_summary_service(
    db: Session = Depends(get_db),
) -> SummaryService:
    return SummaryService(db=db)
