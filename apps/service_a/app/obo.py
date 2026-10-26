from __future__ import annotations

import logging
from functools import lru_cache

import msal
from fastapi import HTTPException, status

from .config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _confidential_client() -> msal.ConfidentialClientApplication:
    return msal.ConfidentialClientApplication(
        client_id=settings.client_id,
        client_credential=settings.client_secret,
        authority=settings.authority,
    )


def acquire_token_for_service_b(user_assertion: str) -> str:
    try:
        result = _confidential_client().acquire_token_on_behalf_of(
            user_assertion=user_assertion,
            scopes=[settings.service_b_scope],
        )
    except Exception as exc:  # msal raises for invalid parameters / network failures
        logger.exception("OBO request to Microsoft Entra ID failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OBO request to Microsoft Entra ID failed: {exc}",
        ) from exc

    access_token = result.get("access_token")
    if not access_token:
        error = result.get("error") or "unknown_error"
        description = result.get("error_description") or "no error description"
        logger.error("OBO to Service B failed: %s - %s", error, description)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": error, "error_description": description},
        )

    logger.info(
        "OBO token acquired for Service B (scope=%s, expires_in=%s)",
        settings.service_b_scope,
        result.get("expires_in"),
    )
    return access_token
