"""Users in the database (D-AUTH-1, D-AUTH-2): authentication, the logged-in user, the demo seed,
and the admin's user management. A provider user has the provider ID their claims are filed
under; a member user (D-MEM-1) the member ID of the patient they are.

Login protection (D-AUTH-2): five failed logins in a row lock the login for 15 minutes (a correct
password then is refused too); a successful login clears the count. A locked or deactivated user
cannot log in; an admin can unlock, deactivate, reactivate and set a new password. Passwords are
10 to 256 characters and not the username."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Role
from app.auth.passwords import DUMMY_HASH, hash_password, verify_password
from app.db.models import Member, Provider, User

LOCK_AFTER = 5  # failed logins in a row
LOCK_FOR = timedelta(minutes=15)
PASSWORD_MIN, PASSWORD_MAX = 10, 256


@dataclass(frozen=True)
class AuthUser:
    username: str
    display_name: str
    role: Role
    provider_id: str | None
    member_id: str | None = None


class AccountLocked(Exception):
    """Too many failed logins: refused until `until` (HTTP 429)."""

    def __init__(self, until: datetime) -> None:
        super().__init__(f"locked until {until.isoformat()}")
        self.until = until


class UserRefused(ValueError):
    """A user change the rules refuse (HTTP 422 or 409)."""


def _user(row: User) -> AuthUser:
    return AuthUser(row.username, row.display_name, Role(row.role), row.provider_id, row.member_id)


def _now() -> datetime:
    return datetime.now(UTC)


def authenticate(session: Session, username: str, password: str) -> AuthUser | None:
    """The active user with this username and password, or None (same work either way). Counts a
    failed login and locks the user after LOCK_AFTER in a row; raises AccountLocked while locked.
    The caller commits."""
    row = session.get(User, username)
    if row is None or not row.active:
        verify_password(password, DUMMY_HASH)
        return None
    if row.locked_until is not None and row.locked_until > _now():
        verify_password(password, DUMMY_HASH)
        raise AccountLocked(row.locked_until)
    if not verify_password(password, row.password_hash):
        row.failed_logins = (row.failed_logins or 0) + 1
        if row.failed_logins >= LOCK_AFTER:
            row.locked_until = _now() + LOCK_FOR
            row.failed_logins = 0
        return None
    row.failed_logins = 0
    row.locked_until = None
    return _user(row)


def active_user(session: Session, username: str) -> AuthUser | None:
    row = session.get(User, username)
    return _user(row) if row is not None and row.active else None


def check_password(password: str, username: str) -> None:
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        raise UserRefused(f"a password has {PASSWORD_MIN} to {PASSWORD_MAX} characters")
    if password.strip().lower() == username.strip().lower():
        raise UserRefused("the password cannot be the username")


def put_user(
    session: Session,
    username: str,
    display_name: str,
    role: Role,
    password: str,
    provider_id: str | None = None,
    member_id: str | None = None,
) -> None:
    """Create or update a user, active and unlocked, with a new password hash (the caller
    commits). The demo seed's path; it does not check the password rules."""
    row = session.get(User, username) or User(username=username)
    row.display_name = display_name
    row.role = role.value
    row.provider_id = provider_id
    row.member_id = member_id
    row.password_hash = hash_password(password)
    row.active = True
    row.failed_logins = 0
    row.locked_until = None
    row.password_changed_at = _now()
    session.add(row)


@dataclass(frozen=True)
class UserInfo:
    """A user as the admin's user list shows them (never the password hash)."""

    username: str
    display_name: str
    role: str
    provider_id: str | None
    member_id: str | None
    active: bool
    locked_until: datetime | None
    password_changed_at: datetime | None
    created_at: datetime | None


def _info(row: User) -> UserInfo:
    locked = row.locked_until if row.locked_until and row.locked_until > _now() else None
    return UserInfo(
        username=row.username,
        display_name=row.display_name,
        role=row.role,
        provider_id=row.provider_id,
        member_id=row.member_id,
        active=bool(row.active),
        locked_until=locked,
        password_changed_at=row.password_changed_at,
        created_at=row.created_at,
    )


def list_users(session: Session) -> list[UserInfo]:
    return [_info(row) for row in session.scalars(select(User).order_by(User.role, User.username))]


def create_user(
    session: Session,
    *,
    username: str,
    display_name: str,
    role: Role,
    password: str,
    provider_id: str | None = None,
    member_id: str | None = None,
) -> UserInfo:
    """A new user (the admin's Users page). A provider user's NPI and a member user's member ID
    must be on file; the other roles have neither. Raises UserRefused."""
    username = username.strip()
    if (
        not username
        or len(username) > 64
        or not username.replace(".", "").replace("-", "").replace("_", "").isalnum()
    ):
        raise UserRefused("a username has 1 to 64 letters, digits, dots, dashes or underscores")
    if session.get(User, username) is not None:
        raise UserRefused(f"the username {username} is taken")
    check_password(password, username)
    if role is Role.PROVIDER:
        if not provider_id or session.get(Provider, provider_id) is None:
            raise UserRefused("a provider user needs the NPI of a provider on file")
        member_id = None
    elif role is Role.MEMBER:
        if not member_id or session.get(Member, member_id) is None:
            raise UserRefused("a member user needs the member ID of a member on file")
        provider_id = None
    else:
        provider_id = member_id = None
    name = display_name.strip()
    if role is Role.PROVIDER and not name:
        provider = session.get(Provider, provider_id)
        name = provider.name if provider else username
    if role is Role.MEMBER and not name:
        member = session.get(Member, member_id)
        name = f"{member.first_name} {member.last_name}" if member else username
    put_user(session, username, name or username, role, password, provider_id, member_id)
    session.flush()
    row = session.get(User, username)
    assert row is not None
    return _info(row)


def _row(session: Session, username: str) -> User:
    row = session.get(User, username)
    if row is None:
        raise LookupError(f"no user {username}")
    return row


def set_password(session: Session, username: str, password: str) -> None:
    """An admin sets a new password; it also unlocks the login."""
    row = _row(session, username)
    check_password(password, username)
    row.password_hash = hash_password(password)
    row.password_changed_at = _now()
    row.failed_logins = 0
    row.locked_until = None


def change_password(session: Session, username: str, current: str, new: str) -> None:
    """A user changes their own password, giving the current one. Raises UserRefused."""
    row = _row(session, username)
    if not verify_password(current, row.password_hash):
        raise UserRefused("the current password is not right")
    if current == new:
        raise UserRefused("the new password is the same as the current one")
    check_password(new, username)
    row.password_hash = hash_password(new)
    row.password_changed_at = _now()


def set_active(session: Session, username: str, active: bool, acting: str) -> None:
    if username == acting and not active:
        raise UserRefused("you cannot deactivate your own login")
    _row(session, username).active = active


def unlock(session: Session, username: str) -> None:
    row = _row(session, username)
    row.failed_logins = 0
    row.locked_until = None
