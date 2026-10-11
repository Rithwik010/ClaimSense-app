"""Session tokens: a JWT signed with HS256 that names the user and their role and expires after
SESSION_HOURS. The API sends it as the COOKIE cookie (httpOnly, SameSite=Strict); API clients may
send it as `Authorization: Bearer <token>` instead."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

ALGORITHM = "HS256"
SESSION_HOURS = 8
COOKIE = "claimsense_session"


class InvalidToken(ValueError):
    """Missing claims, a bad signature, or expired."""


@dataclass(frozen=True)
class TokenClaims:
    username: str
    role: str


def create_token(
    username: str, role: str, secret: str, now: datetime | None = None, hours: int = SESSION_HOURS
) -> str:
    issued = now or datetime.now(UTC)
    payload = {"sub": username, "role": role, "iat": issued, "exp": issued + timedelta(hours=hours)}
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def read_token(token: str, secret: str) -> TokenClaims:
    try:
        payload = jwt.decode(
            token, secret, algorithms=[ALGORITHM], options={"require": ["sub", "role", "exp"]}
        )
    except jwt.InvalidTokenError as exc:  # includes an expired token and a bad signature
        raise InvalidToken(type(exc).__name__) from exc
    return TokenClaims(username=str(payload["sub"]), role=str(payload["role"]))
