"""Logins and roles (D-AUTH-1; replaces the prototype role header of INSTRUCTIONS.md §8.10).

Built as in FastAPI's security tutorial: passwords hashed with Argon2 (pwdlib), a signed JWT
(PyJWT, HS256, SECRET_KEY from .env) that the API sets as an httpOnly, SameSite=Strict cookie for
8 hours. A prototype: no SSO, MFA, password reset or account lockout.
"""

from enum import StrEnum


class Role(StrEnum):
    PROVIDER = "provider"
    REVIEWER = "reviewer"
    ADMIN = "admin"
