"""Users in the database (D-AUTH-1): authentication, the logged-in user, and the demo seed. A
provider user has the provider ID their claims are filed under; a member user (D-MEM-1) the
member ID of the patient they are."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.auth import Role
from app.auth.passwords import DUMMY_HASH, hash_password, verify_password
from app.db.models import User


@dataclass(frozen=True)
class AuthUser:
    username: str
    display_name: str
    role: Role
    provider_id: str | None
    member_id: str | None = None


def _user(row: User) -> AuthUser:
    return AuthUser(row.username, row.display_name, Role(row.role), row.provider_id, row.member_id)


def authenticate(session: Session, username: str, password: str) -> AuthUser | None:
    """The active user with this username and password, or None (same work either way)."""
    row = session.get(User, username)
    if row is None or not row.active:
        verify_password(password, DUMMY_HASH)
        return None
    return _user(row) if verify_password(password, row.password_hash) else None


def active_user(session: Session, username: str) -> AuthUser | None:
    row = session.get(User, username)
    return _user(row) if row is not None and row.active else None


def put_user(
    session: Session,
    username: str,
    display_name: str,
    role: Role,
    password: str,
    provider_id: str | None = None,
    member_id: str | None = None,
) -> None:
    """Create or update a user, active, with a new password hash (the caller commits)."""
    row = session.get(User, username) or User(username=username)
    row.display_name = display_name
    row.role = role.value
    row.provider_id = provider_id
    row.member_id = member_id
    row.password_hash = hash_password(password)
    row.active = True
    session.add(row)
