from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from burnrate.config import Settings, get_settings
from burnrate.db.session import get_db
from burnrate.integrations.enable_banking.client import EnableBankingClient
from burnrate.services.enable_banking_service import EnableBankingService


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

