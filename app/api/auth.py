"""Login, logout and the logged-in user (D-AUTH-1). Login and logout are public; the session is a
signed token in an httpOnly, SameSite=Strict cookie that expires after 8 hours. Logout deletes the
cookie (a copied token stays valid until it expires: prototype). A member user (D-MEM-1) is told
their member ID too; the other roles' answers are as before."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session

from app.api.deps import LoggedInUser, get_session
from app.auth.tokens import COOKIE, SESSION_HOURS, create_token
from app.auth.users import AuthUser, authenticate
from app.core.logging import get_logger
from app.core.settings import Settings, get_settings

router = APIRouter(prefix="/v1/auth", tags=["auth"])
log = get_logger(__name__)


class Login(BaseModel):
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=256)]


class UserView(BaseModel):
    username: str
    display_name: str
    role: str
    provider_id: str | None
    # A member user's member ID; left out for every other role.
    member_id: str | None = Field(default=None, exclude_if=lambda v: v is None)


def _view(user: AuthUser) -> UserView:
    return UserView(
        username=user.username,
        display_name=user.display_name,
        role=user.role.value,
        provider_id=user.provider_id,
        member_id=user.member_id,
    )


@router.post("/login")
def login(
    body: Login,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserView:
    """Checks the username and password and sets the session cookie; 401 for either wrong."""
    if settings.secret_key is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "SECRET_KEY is not set (make demo-users sets it)"
        )
    user = authenticate(session, body.username, body.password)
    if user is None:
        log.info("login_failed")
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Wrong username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_token(user.username, user.role.value, settings.secret_key.get_secret_value())
    response.set_cookie(
        COOKIE,
        token,
        max_age=SESSION_HOURS * 3600,
        httponly=True,
        samesite="strict",
        secure=False,  # the demo runs on http://localhost
        path="/",
    )
    log.info("login", username=user.username, role=user.role.value)
    return _view(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/", httponly=True, samesite="strict")


@router.get("/me")
def me(user: LoggedInUser) -> UserView:
    return _view(user)
