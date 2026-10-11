"""D-AUTH-1: password hashes (Argon2) and session tokens (HS256 JWT, 8 hours)."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.auth.passwords import hash_password, verify_password
from app.auth.tokens import ALGORITHM, SESSION_HOURS, InvalidToken, create_token, read_token

SECRET = "a test secret that is long enough for HS256"


def test_passwords_are_argon2_hashes_that_verify_only_the_right_password() -> None:
    stored = hash_password("correct horse")
    assert stored.startswith("$argon2id$") and "correct horse" not in stored
    assert verify_password("correct horse", stored)
    assert not verify_password("Correct horse", stored)
    assert hash_password("correct horse") != stored  # salted


def test_a_token_names_the_user_and_role_and_expires_after_eight_hours() -> None:
    issued = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)
    token = create_token("reviewer-1", "reviewer", SECRET, now=issued)
    payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM], options={"verify_exp": False})
    assert (payload["sub"], payload["role"]) == ("reviewer-1", "reviewer")
    assert payload["exp"] - payload["iat"] == SESSION_HOURS * 3600
    fresh = create_token("reviewer-1", "reviewer", SECRET)
    assert read_token(fresh, SECRET).username == "reviewer-1"


@pytest.mark.parametrize(
    "token",
    [
        create_token(
            "r", "reviewer", SECRET, now=datetime.now(UTC) - timedelta(hours=8, seconds=1)
        ),
        create_token("r", "reviewer", "another key, not the one the API holds"),
        jwt.encode({"sub": "r", "role": "reviewer"}, SECRET, algorithm=ALGORITHM),  # no expiry
        jwt.encode({"sub": "r", "role": "admin", "exp": 4102444800}, SECRET, algorithm="HS512"),
        "x.y.z",
    ],
    ids=["expired", "other-key", "no-expiry", "other-algorithm", "garbage"],
)
def test_an_invalid_token_is_refused(token: str) -> None:
    with pytest.raises(InvalidToken):
        read_token(token, SECRET)


def test_an_empty_secret_key_is_no_key() -> None:
    from app.core.settings import Settings

    assert Settings(secret_key="").secret_key is None
    assert Settings(secret_key="   ").secret_key is None
    assert Settings(secret_key="k" * 40).secret_key.get_secret_value() == "k" * 40
