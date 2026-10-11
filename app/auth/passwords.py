"""Password hashes: Argon2 through pwdlib (its recommended settings)."""

from pwdlib import PasswordHash

_HASH = PasswordHash.recommended()
# Checked when the username is unknown, so a wrong username takes as long as a wrong password
# (FastAPI's security tutorial).
DUMMY_HASH = _HASH.hash("not a password of anyone")


def hash_password(password: str) -> str:
    return _HASH.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _HASH.verify(password, password_hash)
