"""`make demo-users` (also run by `make demo-reset`): the demo logins (D-AUTH-1).

Two providers, each a provider of the demo data (their NPI is their provider ID) who files some of
the nine demo claims (FILED_BY), two reviewers, one admin, and two members (D-MEM-1): patients of
demo claims whose claims end final in the demo run (MEMBERS). Passwords come from .env
(git-ignored): DEMO_PASSWORD_<USERNAME>, and SECRET_KEY signs the session tokens. A value missing
from .env is generated (random) and written there; nothing is printed but the usernames.

    uv run python -m scripts.demo.users
"""

import os
import secrets
from pathlib import Path

from sqlalchemy.orm import Session

from app.auth import Role
from app.auth.users import put_user
from app.db.models import Member, Provider
from app.db.session import get_engine

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
USERS = {  # username: (role, provider NPI, display name when not a provider)
    "provider1": (Role.PROVIDER, "2829620345", None),
    "provider2": (Role.PROVIDER, "1816701100", None),
    "reviewer1": (Role.REVIEWER, None, "Reviewer One"),
    "reviewer2": (Role.REVIEWER, None, "Reviewer Two"),
    "admin": (Role.ADMIN, None, "Administrator"),
    "member1": (Role.MEMBER, None, None),
    "member2": (Role.MEMBER, None, None),
}
# Each member login's member ID (their name comes from the member record): member1 is the patient
# of claim 01 (approved after review) and 07 (its duplicate, rejected), member2 of claim 04 (partly
# approved after review), so both have final claims once the demo run is through (docs/DEMO.md).
MEMBERS = {"member1": "MBR-000152", "member2": "MBR-000150"}
# Which provider files which demo claim (demo/claims/): provider1 bills claims 01 and 07 itself,
# provider2's practice bills 04 and 06; the rest are split between them.
FILED_BY = {
    "01-approve-quick.json": "provider1",
    "02-pend-standard.json": "provider1",
    "03-deny-full-override.json": "provider1",
    "07-duplicate-of-01.json": "provider1",
    "04-partial-ncci.json": "provider2",
    "05-rule-deny-r15.json": "provider2",
    "06-reject-invalid-npi.json": "provider2",
    "08-scanned-clean.pdf": "provider2",
    "09-scanned-low-confidence.pdf": "provider2",
}


def env_values() -> dict[str, str]:
    """.env as KEY=VALUE lines, overridden by the environment."""
    found = {}
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and not key.strip().startswith("#"):
                found[key.strip()] = value.strip().strip('"').strip("'")
    return found | {k: v for k, v in os.environ.items() if k in found or k.startswith("DEMO_")}


def password_key(username: str) -> str:
    return f"DEMO_PASSWORD_{username.upper()}"


def password(username: str) -> str:
    """A demo user's password from .env (for the scripts that log in)."""
    value = env_values().get(password_key(username))
    if not value:
        raise SystemExit(f"{password_key(username)} is not in .env: run make demo-users")
    return value


def ensure_env() -> list[str]:
    """Write SECRET_KEY and any missing demo password to .env; returns the keys written."""
    values = env_values()
    wanted = ["SECRET_KEY", *(password_key(u) for u in USERS)]
    missing = [key for key in wanted if not values.get(key)]
    if missing:
        lines = [
            f"{key}={secrets.token_hex(32) if key == 'SECRET_KEY' else secrets.token_urlsafe(12)}"
            for key in missing
        ]
        existing = ENV.read_text(encoding="utf-8") if ENV.exists() else ""
        prefix = "" if not existing or existing.endswith("\n") else "\n"
        with ENV.open("a", encoding="utf-8") as env:
            header = "# Demo logins (make demo-users, D-AUTH-1)\n"
            env.write(prefix + header + "\n".join(lines) + "\n")
        ENV.chmod(0o600)
    return missing


def seed_users(session: Session) -> None:
    for username, (role, npi, name) in USERS.items():
        if npi is not None:
            provider = session.get(Provider, npi)
            if provider is None:
                raise SystemExit(f"{username}: provider {npi} is not in the demo data")
            name = provider.name
        member_id = MEMBERS.get(username)
        if member_id is not None:
            member = session.get(Member, member_id)
            if member is None:
                raise SystemExit(f"{username}: member {member_id} is not in the demo data")
            name = f"{member.first_name} {member.last_name}"
        put_user(session, username, name or username, role, password(username), npi, member_id)
    session.commit()


def main() -> None:
    written = ensure_env()
    if written:
        print(f"- .env: wrote {', '.join(written)}")
    with Session(get_engine()) as session:
        seed_users(session)
    print(f"- users: {', '.join(USERS)} (passwords in .env: DEMO_PASSWORD_<USERNAME>)")


if __name__ == "__main__":
    main()
