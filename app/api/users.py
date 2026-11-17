"""User management (D-AUTH-2): the admin's list of logins, a new login, a new password, unlocking
and deactivating. Admins only; each change is logged with the admin and the username (never a
password)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, StringConstraints

from app.api.deps import AdminUser, SessionDep
from app.auth import Role
from app.auth.users import (
    UserInfo,
    UserRefused,
    create_user,
    list_users,
    set_active,
    set_password,
    unlock,
)
from app.core.logging import get_logger

router = APIRouter(prefix="/v1/users", tags=["users"])
log = get_logger(__name__)

Text64 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class UserInfoView(BaseModel):
    username: str
    display_name: str
    role: str
    provider_id: str | None
    member_id: str | None
    active: bool
    locked_until: datetime | None
    password_changed_at: datetime | None
    created_at: datetime | None


class NewUser(BaseModel):
    username: Text64
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=128)] = ""
    role: Role
    password: Annotated[str, StringConstraints(min_length=1, max_length=256)]
    provider_id: Annotated[str, StringConstraints(pattern=r"^[0-9]{10}$")] | None = None
    member_id: Annotated[str, StringConstraints(strip_whitespace=True, max_length=32)] | None = None


class NewPassword(BaseModel):
    password: Annotated[str, StringConstraints(min_length=1, max_length=256)]


class Active(BaseModel):
    active: bool


def _view(info: UserInfo) -> UserInfoView:
    return UserInfoView.model_validate(info, from_attributes=True)


def _refused(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))


@router.get("")
def users(session: SessionDep, _admin: AdminUser) -> list[UserInfoView]:
    return [_view(info) for info in list_users(session)]


@router.post("", status_code=status.HTTP_201_CREATED)
def new_user(body: NewUser, session: SessionDep, admin: AdminUser) -> UserInfoView:
    try:
        info = create_user(
            session,
            username=body.username,
            display_name=body.display_name,
            role=body.role,
            password=body.password,
            provider_id=body.provider_id,
            member_id=body.member_id,
        )
    except UserRefused as exc:
        session.rollback()
        raise _refused(exc) from exc
    session.commit()
    log.info("user_created", by=admin.username, username=info.username, role=info.role)
    return _view(info)


@router.post("/{username}/password", status_code=status.HTTP_204_NO_CONTENT)
def new_password(username: str, body: NewPassword, session: SessionDep, admin: AdminUser) -> None:
    try:
        set_password(session, username, body.password)
    except (UserRefused, LookupError) as exc:
        session.rollback()
        raise _refused(exc) from exc
    session.commit()
    log.info("password_set_by_admin", by=admin.username, username=username)


@router.post("/{username}/active", status_code=status.HTTP_204_NO_CONTENT)
def active(username: str, body: Active, session: SessionDep, admin: AdminUser) -> None:
    try:
        set_active(session, username, body.active, admin.username)
    except (UserRefused, LookupError) as exc:
        session.rollback()
        raise _refused(exc) from exc
    session.commit()
    log.info("user_active_set", by=admin.username, username=username, active=body.active)


@router.post("/{username}/unlock", status_code=status.HTTP_204_NO_CONTENT)
def unlock_user(username: str, session: SessionDep, admin: AdminUser) -> None:
    try:
        unlock(session, username)
    except LookupError as exc:
        raise _refused(exc) from exc
    session.commit()
    log.info("user_unlocked", by=admin.username, username=username)
