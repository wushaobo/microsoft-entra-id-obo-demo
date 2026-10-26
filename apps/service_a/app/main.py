from __future__ import annotations

import logging
import time

import httpx
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .auth import Principal, require_token
from .config import settings
from .log_utils import one_line
from .logging_config import configure_logging
from .obo import acquire_token_for_service_b

configure_logging()

logger = logging.getLogger(__name__)

app = FastAPI(title="Service A", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/data")
def get_data(_: Principal = Depends(require_token)) -> dict[str, str]:
    return {
        "data": "This message is from Service A.",
        "source": "service-a",
    }


@app.get("/api/data-from-downstream")
def get_data_from_downstream(
    principal: Principal = Depends(require_token),
) -> dict[str, str]:
    request_id = principal.request_id
    downstream_url = f"{settings.service_b_base_url}/api/data"

    b_access_token = acquire_token_for_service_b(
        principal.access_token,
        request_id,
    )

    started = time.perf_counter()
    try:
        response = httpx.get(
            downstream_url,
            headers={
                "Authorization": f"Bearer {b_access_token}",
                "X-Request-ID": request_id,
            },
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        logger.warning(
            "DOWNSTREAM FAIL | rid=%s | GET %s | duration_ms=%.1f | error=%s",
            request_id,
            downstream_url,
            (time.perf_counter() - started) * 1000,
            one_line(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to call Service B: {exc}",
        ) from exc

    duration_ms = (time.perf_counter() - started) * 1000

    if response.is_error:
        logger.warning(
            "DOWNSTREAM FAIL | rid=%s | GET %s | status=%s | "
            "duration_ms=%.1f | body=%s",
            request_id,
            downstream_url,
            response.status_code,
            duration_ms,
            one_line(response.text),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "service_b_error",
                "status_code": response.status_code,
                "body": response.text[:1000],
            },
        )

    try:
        payload = response.json()
    except ValueError as exc:
        logger.warning(
            "DOWNSTREAM FAIL | rid=%s | GET %s | status=%s | "
            "duration_ms=%.1f | reason=invalid_json | body=%s",
            request_id,
            downstream_url,
            response.status_code,
            duration_ms,
            one_line(response.text),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "service_b_error",
                "body": response.text[:1000],
            },
        ) from exc

    if not isinstance(payload, dict) or "data" not in payload:
        logger.warning(
            "DOWNSTREAM FAIL | rid=%s | GET %s | status=%s | "
            "duration_ms=%.1f | reason=missing_data | body=%s",
            request_id,
            downstream_url,
            response.status_code,
            duration_ms,
            one_line(response.text),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "service_b_error",
                "body": response.text[:1000],
            },
        )

    logger.info(
        "DOWNSTREAM OK | rid=%s | GET %s | status=%s | duration_ms=%.1f | bytes=%d",
        request_id,
        downstream_url,
        response.status_code,
        duration_ms,
        len(response.content),
    )

    return {
        "data": str(payload["data"]),
        "source": str(payload.get("source", "service-b")),
    }
