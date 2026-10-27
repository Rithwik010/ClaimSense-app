"""Logins and roles (D-AUTH-1; replaces the prototype role header of INSTRUCTIONS.md §8.10).

Built as in FastAPI's security tutorial: passwords hashed with Argon2 (pwdlib), a signed JWT
(PyJWT, HS256, SECRET_KEY from .env) that the API sets as an httpOnly, SameSite=Strict cookie for
8 hours. A prototype: no SSO, MFA, password reset or account lockout.

A member (D-MEM-1) is a patient: their login is linked to their member ID and opens only their own
claims, EOBs, benefits and profile, through their own routes (/v1/member/...); the claims, review,
plan and metrics endpoints never admit the member role.
"""

from enum import StrEnum


class Role(StrEnum):
    PROVIDER = "provider"
    REVIEWER = "reviewer"
    ADMIN = "admin"
    MEMBER = "member"
