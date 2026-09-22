"""Reference records the rules read, as plain values. The caller loads them from the database, so
the rules stay pure functions with no database access of their own (§8.3)."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class MemberRef:
    member_id: str
    plan_id: str
    coverage_start: date
    coverage_end: date | None  # inclusive; None = open-ended

    def covers(self, day: date) -> bool:
        return self.coverage_start <= day and (
            self.coverage_end is None or day <= self.coverage_end
        )
