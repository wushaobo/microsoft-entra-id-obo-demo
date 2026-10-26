from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

SERVICE_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(SERVICE_ROOT / ".env")


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing required environment variable {name!r}. "
            f"Copy {SERVICE_ROOT / 'env.example'} to .env and fill it in."
        )
    return value


def _optional(name: str, default: str) -> str:
    return os.getenv(name, default).strip() or default


def _csv(name: str, default: str) -> tuple[str, ...]:
    return tuple(
        item.strip() for item in _optional(name, default).split(",") if item.strip()
    )


@dataclass(frozen=True)
class Settings:
    tenant_id: str
    client_id: str
    client_secret: str
    required_scope: str
    extra_audiences: tuple[str, ...]
    cors_origins: tuple[str, ...]
    service_b_base_url: str
    service_b_scope: str

    @property
    def authority(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}"

    @property
    def accepted_audiences(self) -> tuple[str, ...]:
        return tuple(
            {self.client_id, f"api://{self.client_id}", *self.extra_audiences}
        )


def load_settings() -> Settings:
    extra_audience = _optional("ENTRA_AUDIENCE", "")
    return Settings(
        tenant_id=_required("ENTRA_TENANT_ID"),
        client_id=_required("ENTRA_CLIENT_ID"),
        client_secret=_required("ENTRA_CLIENT_SECRET"),
        required_scope=_optional("ENTRA_REQUIRED_SCOPE", "access_as_user"),
        extra_audiences=(extra_audience,) if extra_audience else (),
        cors_origins=_csv("CORS_ORIGINS", "http://localhost:5173"),
        service_b_base_url=_optional(
            "SERVICE_B_BASE_URL", "http://localhost:8002"
        ).rstrip("/"),
        service_b_scope=_required("SERVICE_B_SCOPE"),
    )


settings = load_settings()
