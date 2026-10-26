from __future__ import annotations

import httpx
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .auth import Principal, require_token
from .config import settings
from .obo import acquire_token_for_service_b

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
    b_access_token = acquire_token_for_service_b(principal.access_token)

    try:
        response = httpx.get(
            f"{settings.service_b_base_url}/api/data",
            headers={"Authorization": f"Bearer {b_access_token}"},
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to call Service B: {exc}",
        ) from exc

    if response.is_error:
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
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "service_b_error",
                "body": response.text[:1000],
            },
        ) from exc

    if not isinstance(payload, dict) or "data" not in payload:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "service_b_error",
                "body": response.text[:1000],
            },
        )

    return {
        "data": str(payload["data"]),
        "source": str(payload.get("source", "service-b")),
    }
