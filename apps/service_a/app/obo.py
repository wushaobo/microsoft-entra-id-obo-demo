from __future__ import annotations

import logging
from functools import lru_cache

import msal
from fastapi import HTTPException, status

from .config import settings
from .log_utils import one_line, token_tail

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _confidential_client() -> msal.ConfidentialClientApplication:
    return msal.ConfidentialClientApplication(
        client_id=settings.client_id,
        client_credential=settings.client_secret,
        authority=settings.authority,
    )


def acquire_token_for_service_b(user_assertion: str, request_id: str) -> str:
    logger.info(
        "OBO START | rid=%s | scope=%s | assertion_tail=%s",
        request_id,
        settings.service_b_scope,
        token_tail(user_assertion),
    )

    try:
        result = _confidential_client().acquire_token_on_behalf_of(
            user_assertion=user_assertion,
            scopes=[settings.service_b_scope],
        )
    except Exception as exc:  # msal raises for invalid parameters / network failures
        logger.exception(
            "OBO FAIL | rid=%s | scope=%s | reason=exception | error=%s",
            request_id,
            settings.service_b_scope,
            one_line(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OBO request to Microsoft Entra ID failed: {exc}",
        ) from exc

    access_token = result.get("access_token")
    if not access_token:
        error = result.get("error") or "unknown_error"
        description = result.get("error_description") or "no error description"
        logger.warning(
            "OBO FAIL | rid=%s | scope=%s | error=%s | suberror=%s | "
            "error_codes=%s | correlation_id=%s | trace_id=%s | "
            "error_uri=%s | description=%s",
            request_id,
            settings.service_b_scope,
            error,
            result.get("suberror", "-"),
            result.get("error_codes", "-"),
            result.get("correlation_id", "-"),
            result.get("trace_id", "-"),
            result.get("error_uri", "-"),
            one_line(description),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": error, "error_description": description},
        )

    logger.info(
        "OBO OK | rid=%s | scope=%s | token_source=%s | expires_in=%s | "
        "correlation_id=%s | downstream_token_tail=%s",
        request_id,
        settings.service_b_scope,
        result.get("token_source", "-"),
        result.get("expires_in", "-"),
        result.get("correlation_id", "-"),
        token_tail(access_token),
    )
    return access_token
