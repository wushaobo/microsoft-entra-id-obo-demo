from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError

from .config import settings
from .log_utils import one_line, token_tail

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED_HEADERS = {"WWW-Authenticate": "Bearer"}

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


@dataclass(frozen=True)
class Principal:
    claims: dict[str, Any]
    access_token: str
    request_id: str


def _request_id(request: Request) -> str:
    inbound = request.headers.get("x-request-id", "").strip()
    if inbound and _REQUEST_ID_PATTERN.fullmatch(inbound):
        return inbound
    return uuid.uuid4().hex[:12]


def _token_kid(token: str) -> str:
    try:
        return one_line(jwt.get_unverified_header(token).get("kid") or "-", 100)
    except (jwt.PyJWTError, ValueError, TypeError):
        return "-"


def _claim_fields(claims: dict[str, Any]) -> str:
    return (
        f"aud={claims.get('aud')} | iss={claims.get('iss')} | "
        f"scp={claims.get('scp')} | oid={claims.get('oid') or claims.get('sub')} | "
        f"tid={claims.get('tid')} | ver={claims.get('ver')} | "
        f"azp={claims.get('azp') or claims.get('appid')}"
    )


def _log_auth_failure(
    request: Request,
    request_id: str,
    reason: str,
    token: str | None = None,
    claims: dict[str, Any] | None = None,
    **extra: object,
) -> None:
    fields = [
        f"AUTH FAIL | rid={request_id}",
        f"{request.method} {request.url.path}",
        f"reason={reason}",
    ]
    for key, value in extra.items():
        fields.append(f"{key}={one_line(value, 200)}")
    if token is not None:
        fields.append(f"token_tail={token_tail(token)}")
        fields.append(f"kid={_token_kid(token)}")
    if claims is not None:
        fields.append(_claim_fields(claims))
    logger.warning(" | ".join(fields))


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


def _accepted_issuers(claims: dict[str, Any]) -> list[str]:
    """Accept v2 tokens and v1 tokens issued by the token's tenant.

    The API app registration's "accessTokenAcceptedVersion" manifest value
    decides whether Entra issues a v2 issuer or the legacy sts.windows.net
    issuer for tokens whose audience is this API. The tenant itself is checked
    separately below.
    """
    issuers = {str(_openid_metadata()["issuer"]).rstrip("/")}
    tenant_id = str(claims.get("tid", "")).strip()
    if tenant_id:
        issuers.add(f"https://sts.windows.net/{tenant_id}".rstrip("/"))
    return sorted(issuers)


def require_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    request_id = _request_id(request)

    if credentials is None or credentials.scheme.lower() != "bearer":
        _log_auth_failure(request, request_id, "missing_bearer_token")
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
            options={
                "require": ["exp", "iat", "aud", "iss"],
                # Issuer is validated below so both v1 and v2 tokens work.
                "verify_iss": False,
            },
        )
    except (PyJWKClientConnectionError, httpx.HTTPError) as exc:
        _log_auth_failure(
            request,
            request_id,
            "jwks_unavailable",
            token=token,
            error=one_line(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to fetch Microsoft Entra ID signing keys: {exc}",
        ) from exc
    except jwt.PyJWTError as exc:
        _log_auth_failure(
            request,
            request_id,
            "token_decode_failed",
            token=token,
            error=one_line(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid access token: {exc}",
            headers=_UNAUTHORIZED_HEADERS,
        ) from exc

    issuer = str(claims.get("iss", "")).rstrip("/")
    accepted_issuers = _accepted_issuers(claims)
    if issuer not in accepted_issuers:
        _log_auth_failure(
            request,
            request_id,
            "issuer_mismatch",
            token=token,
            claims=claims,
            issuer=issuer,
            accepted_issuers=accepted_issuers,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                f"Invalid access token: unexpected issuer {issuer!r} "
                f"(ver={claims.get('ver')!r}, accepted issuers: "
                f"{accepted_issuers})."
            ),
            headers=_UNAUTHORIZED_HEADERS,
        )

    if str(claims.get("tid", "")).lower() != settings.tenant_id.lower():
        _log_auth_failure(
            request,
            request_id,
            "tenant_mismatch",
            token=token,
            claims=claims,
            expected_tenant=settings.tenant_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token was issued by an unexpected tenant.",
            headers=_UNAUTHORIZED_HEADERS,
        )

    scopes = set(str(claims.get("scp", "")).split())
    if settings.required_scope not in scopes:
        _log_auth_failure(
            request,
            request_id,
            "scope_missing",
            token=token,
            claims=claims,
            required_scope=settings.required_scope,
            scopes=sorted(scopes) or "none",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Access token is missing required scope "
                f"{settings.required_scope!r} (token scopes: "
                f"{sorted(scopes) or 'none'})."
            ),
        )

    logger.info(
        "AUTH OK | rid=%s | %s %s | scheme=%s | token_tail=%s | kid=%s | %s",
        request_id,
        request.method,
        request.url.path,
        credentials.scheme,
        token_tail(token),
        signing_key.key_id or "-",
        _claim_fields(claims),
    )
    return Principal(claims=claims, access_token=token, request_id=request_id)
