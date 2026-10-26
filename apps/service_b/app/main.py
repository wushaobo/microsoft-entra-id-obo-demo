from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import Principal, require_token
from .config import settings

app = FastAPI(title="Service B", version="0.1.0")

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
        "data": "This message is from Service B.",
        "source": "service-b",
    }
