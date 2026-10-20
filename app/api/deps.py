"""Request dependencies. Tests override `get_engine`, `get_decision_model`, `get_retriever` and
`get_today`. Every endpoint but login, logout and /health needs a logged-in user of the right role
(D-AUTH-1)."""

from collections.abc import Callable, Iterator
from datetime import date
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.auth import Role
from app.auth.tokens import COOKIE, InvalidToken, read_token
from app.auth.users import AuthUser, active_user
from app.core.settings import Settings, get_settings
from app.db.session import get_engine
from app.ml.client import DecisionModel, OllamaDecisionModel
from app.rag.retrieve import CriteriaRetriever, ExactCriteriaRetriever, Retriever


def get_session(engine: Annotated[Engine, Depends(get_engine)]) -> Iterator[Session]:
    """One session per request; anything not committed is rolled back when it closes."""
    with Session(engine) as session:
        yield session


def get_decision_model(settings: Annotated[Settings, Depends(get_settings)]) -> DecisionModel:
    return OllamaDecisionModel(settings.ollama_url, settings.model_name)


@lru_cache
def get_retriever() -> Retriever:
    """One retriever per process, for the pipeline's policy set (D-POL-2): the v2 exact lookup, or
    v1's similarity ranking (its embedding model loads on the first query)."""
    from qdrant_client import QdrantClient

    from app.rag.embedding import FastEmbedder

    settings = get_settings()
    client = QdrantClient(url=settings.qdrant_url)
    if settings.policy_set == "v2":
        return ExactCriteriaRetriever(client)
    return CriteriaRetriever(
        client,
        FastEmbedder(settings.embedding_model, settings.embedding_cache_dir),
        top_k=settings.rag_top_k,
        min_score=settings.rag_min_score,
    )


def get_today() -> date:
    """Today on the API's clock: it picks the member's current benefit year (D7, D-MEM-3)."""
    return date.today()


def _token(request: Request) -> str | None:
    """The session token: an `Authorization: Bearer` header (API clients) or the session cookie
    (the web app)."""
    scheme, _, credentials = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and credentials:
        return credentials
    return request.cookies.get(COOKIE)


def current_user(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthUser:
    """The logged-in user (D-AUTH-1): 401 without a valid, unexpired token of an active user whose
    role is still the token's."""
    token = _token(request)
    if token is None:
        raise _unauthorized("Not logged in")
    if settings.secret_key is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "SECRET_KEY is not set (make demo-users sets it)"
        )
    try:
        claims = read_token(token, settings.secret_key.get_secret_value())
    except InvalidToken as exc:
        raise _unauthorized("The session has expired or is not valid; log in again") from exc
    user = active_user(session, claims.username)
    if user is None or user.role.value != claims.role:
        raise _unauthorized("The session has expired or is not valid; log in again")
    return user


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"}
    )


def require(*allowed: Role) -> Callable[..., AuthUser]:
    """A dependency admitting only users of the given roles (403 for any other role)."""
    names = " or ".join(role.value for role in allowed)

    def check(user: Annotated[AuthUser, Depends(current_user)]) -> AuthUser:
        if user.role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, f"a {user.role.value} cannot do this; it needs {names}"
            )
        return user

    return check


ProviderUser = Annotated[AuthUser, Depends(require(Role.PROVIDER))]
ReviewerUser = Annotated[AuthUser, Depends(require(Role.REVIEWER))]
StaffUser = Annotated[AuthUser, Depends(require(Role.REVIEWER, Role.ADMIN))]
AdminUser = Annotated[AuthUser, Depends(require(Role.ADMIN))]
# The claims endpoints' users: a provider gets their own view, anyone else the staff view, so a
# member is never admitted here (403); a member has their own routes (app/api/member.py, D-MEM-2).
AnyUser = Annotated[AuthUser, Depends(require(Role.PROVIDER, Role.REVIEWER, Role.ADMIN))]
member_only = require(Role.MEMBER)  # also the member router's own guard (one check per request)
MemberUser = Annotated[AuthUser, Depends(member_only)]
LoggedInUser = Annotated[AuthUser, Depends(require(*Role))]  # any role: who is logged in
