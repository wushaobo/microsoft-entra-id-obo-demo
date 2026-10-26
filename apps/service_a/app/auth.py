from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError

from .config import settings

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED_HEADERS = {"WWW-Authenticate": "Bearer"}


@dataclass(frozen=True)
class Principal:
    claims: dict[str, Any]
    access_token: str


@lru_cache(maxsize=1)
def _openid_metadata() -> dict[str, Any]:
    url = f"{settings.authority}/v2.0/.well-known/openid-configuration"
    response = httpx.get(url, timeout=10.0)
    response.raise_for_status()
    return response.json()


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    return PyJWKClient(
        _openid_metadata()["jwks_uri"],
        cache_keys=True,
        lifespan=300,
        timeout=10,
    )


def require_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
            headers=_UNAUTHORIZED_HEADERS,
        )

    token = credentials.credentials
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=list(settings.accepted_audiences),
            issuer=_openid_metadata()["issuer"],
            options={"require": ["exp", "iat", "aud", "iss"]},
        )
    except (PyJWKClientConnectionError, httpx.HTTPError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to fetch Microsoft Entra ID signing keys: {exc}",
        ) from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid access token: {exc}",
            headers=_UNAUTHORIZED_HEADERS,
        ) from exc

    if str(claims.get("tid", "")).lower() != settings.tenant_id.lower():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token was issued by an unexpected tenant.",
            headers=_UNAUTHORIZED_HEADERS,
        )

    scopes = set(str(claims.get("scp", "")).split())
    if settings.required_scope not in scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Access token is missing required scope "
                f"{settings.required_scope!r} (token scopes: "
                f"{sorted(scopes) or 'none'})."
            ),
        )

    logger.info(
        "Authenticated token aud=%s scp=%s tid=%s oid=%s",
        claims.get("aud"),
        claims.get("scp"),
        claims.get("tid"),
        claims.get("oid") or claims.get("sub"),
    )
    return Principal(claims=claims, access_token=token)
