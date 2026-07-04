"""
Authentication and authorization utilities.

- JWT access / refresh token creation and verification.
- Password hashing via passlib bcrypt.
- FastAPI dependency for extracting and validating the current user.
- Admin-key guard for admin/scheduler endpoints.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, Header, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import AuthenticationError, AuthorizationError

# ── Password hashing ─────────────────────────────────────────────────────────

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ── JWT helpers ───────────────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


def create_access_token(subject: str | int, extra: dict[str, Any] | None = None) -> str:
    """Create a short-lived JWT access token."""
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": expires,
        "type": "access",
        **(extra or {}),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str | int) -> str:
    """Create a long-lived JWT refresh token."""
    now = datetime.now(UTC)
    expires = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": expires,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT. Raises AuthenticationError on invalid/expired tokens."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError as exc:
        raise AuthenticationError("Invalid or expired token") from exc


# ── FastAPI dependencies ──────────────────────────────────────────────────────


class TokenData:
    """Lightweight holder for decoded JWT claims."""

    def __init__(self, user_id: int, role: str) -> None:
        self.user_id = user_id
        self.role = role

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> TokenData:
    """FastAPI dependency: extracts and validates the Bearer JWT."""
    if credentials is None:
        raise AuthenticationError("Authentication required")
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise AuthenticationError("Invalid token type")
    try:
        user_id = int(payload["sub"])
        role = payload.get("role", "user")
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("Malformed token payload") from exc
    return TokenData(user_id=user_id, role=role)


async def get_current_admin(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    """FastAPI dependency: requires admin role in the JWT."""
    if not current_user.is_admin:
        raise AuthorizationError("Admin role required")
    return current_user


async def require_admin_key(x_admin_key: str = Header(alias="X-Admin-Key")) -> None:
    """FastAPI dependency: validates the static X-Admin-Key header for admin endpoints.

    Can be used alongside or instead of JWT admin role depending on the endpoint.
    """
    if x_admin_key != settings.ADMIN_API_KEY:
        raise AuthorizationError("Invalid admin API key")
