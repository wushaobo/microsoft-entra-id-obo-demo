from __future__ import annotations

import httpx
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

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


@app.get("/api/message", response_class=PlainTextResponse)
def message(_: Principal = Depends(require_token)) -> str:
    return "This message is from Service A."


@app.get("/api/message-from-b")
def message_from_b(principal: Principal = Depends(require_token)) -> dict[str, object]:
    b_access_token = acquire_token_for_service_b(principal.access_token)

    try:
        response = httpx.get(
            f"{settings.service_b_base_url}/api/message",
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

    return {
        "message": response.text,
        "source": "service-b",
        "via": "service-a-obo",
        "upstream_status": response.status_code,
    }
