"""Reference-data generator (P2.2, INSTRUCTIONS.md §9.4).

Members (~500, some terminated or not yet started), providers (~100 with valid NPIs, some pending
enrollment or out of network), authorizations (~150, some expired or for the wrong code), other
coverage (~50), accumulators and visit usage. Rows match the tables in `app/db/models.py` so the
seed loader (P2.1) can insert them unchanged. Deterministic for a given seed.

    uv run python -m training.generate.reference [--seed N] [--out DIR]
"""

import argparse
import random
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from faker import Faker

from app.db.curated import CuratedData, load_curated
from training.generate.common import (
    DEFAULT_SEED,
    DOS_END,
    DOS_START,
    GENERATED_DIR,
    PERIOD_END,
    PERIOD_START,
    make_npi,
    make_tin,
    write_json,
    write_jsonl,
)

GENERATOR_VERSION = "reference-v1"

MEMBER_COUNT = 500
PLAN_WEIGHTS = {
    "PLN-PPO-GOLD": 25,
    "PLN-PPO-SILVER": 25,
    "PLN-HMO": 20,
    "PLN-EPO": 15,
    "PLN-HDHP": 15,
}
# Coverage status share (percent): the rest are active for the whole dates-of-service window.
TERMINATED_IN_WINDOW, TERMINATED_BEFORE_WINDOW, STARTS_IN_WINDOW = 5, 2, 3

# Providers per type: 100 in total.
PROVIDER_TYPE_COUNTS = {
    "PRIMARY_CARE": 22,
    "RADIOLOGY": 7,
    "CARDIOLOGY": 5,
    "NEUROLOGY": 5,
    "SLEEP_MEDICINE": 5,
    "ALLERGY_IMMUNOLOGY": 5,
    "PSYCHOLOGY": 5,
    "PAIN_MEDICINE": 7,
    "OPHTHALMOLOGY": 5,
    "GASTROENTEROLOGY": 6,
    "VASCULAR_SURGERY": 5,
    "PLASTIC_SURGERY": 5,
    "PODIATRY": 5,
    "PHYSICAL_THERAPY": 7,
    "WOUND_CARE": 6,
}
PENDING_ENROLLMENT = 8
OUT_OF_NETWORK_SHARE = 0.15
MIN_IN_NETWORK_PER_TYPE = 2

AUTH_COUNT = 150
AUTH_EXPIRED_SHARE, AUTH_WRONG_CODE_SHARE = 0.12, 0.08
OTHER_COVERAGE_COUNT = 50
REHAB_USAGE_COUNT = 80

CREDENTIALS = {
    "PSYCHOLOGY": "PhD",
    "PODIATRY": "DPM",
    "PHYSICAL_THERAPY": "DPT",
}
OTHER_PAYERS = [
    "Northwind Health Plan",
    "Blue Harbor Mutual",
    "Summit Benefit Trust",
    "Lakeside Employers Health",
    "Cedar Valley Insurance",
]


@dataclass
class ReferenceData:
    members: list[dict[str, Any]] = field(default_factory=list)
    providers: list[dict[str, Any]] = field(default_factory=list)
    provider_networks: list[dict[str, Any]] = field(default_factory=list)
    authorizations: list[dict[str, Any]] = field(default_factory=list)
    other_coverage: list[dict[str, Any]] = field(default_factory=list)
    accumulators: list[dict[str, Any]] = field(default_factory=list)
    visit_usage: list[dict[str, Any]] = field(default_factory=list)

    def tables(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "members": self.members,
            "providers": self.providers,
            "provider_networks": self.provider_networks,
            "authorizations": self.authorizations,
            "other_coverage": self.other_coverage,
            "accumulators": self.accumulators,
            "visit_usage": self.visit_usage,
        }


def _random_day(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def _coverage(rng: random.Random) -> tuple[date, date | None, str]:
    roll = rng.randint(1, 100)
    if roll <= TERMINATED_IN_WINDOW:
        end = _random_day(rng, DOS_START + timedelta(days=10), DOS_END - timedelta(days=20))
        return date(2025, 1, 1), end, "TERMINATED_IN_WINDOW"
    if roll <= TERMINATED_IN_WINDOW + TERMINATED_BEFORE_WINDOW:
        return date(2025, 1, 1), date(2026, 6, 30), "TERMINATED_BEFORE_WINDOW"
    if roll <= TERMINATED_IN_WINDOW + TERMINATED_BEFORE_WINDOW + STARTS_IN_WINDOW:
        return rng.choice([date(2026, 11, 1), date(2026, 12, 1)]), None, "STARTS_IN_WINDOW"
    start = rng.choice([date(2024, 1, 1), date(2025, 1, 1), date(2026, 1, 1)])
    return start, None, "ACTIVE"


def _members(rng: random.Random, fake: Faker) -> tuple[list[dict[str, Any]], Counter[str]]:
    plans = rng.choices(list(PLAN_WEIGHTS), weights=list(PLAN_WEIGHTS.values()), k=MEMBER_COUNT)
    statuses: Counter[str] = Counter()
    members = []
    for number, plan_id in enumerate(plans, start=1):
        sex = rng.choice("FM")
        first = fake.first_name_female() if sex == "F" else fake.first_name_male()
        start, end, status = _coverage(rng)
        statuses[status] += 1
        members.append(
            {
                "member_id": f"MBR-{number:06d}",
                "plan_id": plan_id,
                "first_name": first,
                "last_name": fake.last_name(),
                "date_of_birth": _random_day(rng, date(1946, 1, 1), date(2019, 12, 31)),
                "sex": sex,
                "address_line": fake.street_address(),
                "city": fake.city(),
                "state": fake.state_abbr(include_territories=False),
                "zip_code": fake.zipcode(),
                "coverage_start": start,
                "coverage_end": end,
            }
        )
    return members, statuses


def _providers(
    rng: random.Random, fake: Faker, curated: CuratedData
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    npis: set[str] = set()
    tins: set[str] = set()
    providers = []
    for provider_type, count in PROVIDER_TYPE_COUNTS.items():
        for _ in range(count):
            credential = CREDENTIALS.get(provider_type, rng.choice(["MD", "MD", "DO"]))
            providers.append(
                {
                    "npi": make_npi(rng, npis),
                    "tin": make_tin(rng, tins),
                    "name": f"{fake.first_name()} {fake.last_name()}, {credential}",
                    "provider_type": provider_type,
                    "enrollment_status": "ENROLLED",
                }
            )
    for provider in rng.sample(providers, PENDING_ENROLLMENT):
        provider["enrollment_status"] = "PENDING"

    networks = []
    for plan_id in curated.plans:
        for provider_type in PROVIDER_TYPE_COUNTS:
            group = [p for p in providers if p["provider_type"] == provider_type]
            flags = [rng.random() >= OUT_OF_NETWORK_SHARE for _ in group]
            enrolled_in = [
                i for i, p in enumerate(group) if flags[i] and p["enrollment_status"] == "ENROLLED"
            ]
            for i, p in enumerate(group):  # keep enough enrolled in-network providers per type
                if len(enrolled_in) >= MIN_IN_NETWORK_PER_TYPE:
                    break
                if p["enrollment_status"] == "ENROLLED" and not flags[i]:
                    flags[i] = True
                    enrolled_in.append(i)
            networks.extend(
                {"npi": p["npi"], "plan_id": plan_id, "in_network": flags[i]}
                for i, p in enumerate(group)
            )
    return providers, networks


def _active_in_window(member: dict[str, Any]) -> bool:
    end = member["coverage_end"]
    return member["coverage_start"] <= DOS_START and (end is None or end >= DOS_END)


def _authorizations(
    rng: random.Random,
    curated: CuratedData,
    members: list[dict[str, Any]],
    providers: list[dict[str, Any]],
    networks: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], Counter[str]]:
    in_network = {(n["npi"], n["plan_id"]) for n in networks if n["in_network"]}
    active = [m for m in members if _active_in_window(m)]
    kinds: Counter[str] = Counter()
    auths = []
    for number in range(1, AUTH_COUNT + 1):
        member = rng.choice(active)
        plan_id = member["plan_id"]
        codes = sorted(c for c in curated.scope if curated.auth_required(plan_id, c))
        code = rng.choice(codes)
        entry = curated.scope[code]
        candidates = [
            p
            for p in providers
            if p["provider_type"] in entry.provider_types
            and p["enrollment_status"] == "ENROLLED"
            and (p["npi"], plan_id) in in_network
        ]
        provider = rng.choice(candidates)
        roll = rng.random()
        if roll < AUTH_EXPIRED_SHARE:
            end = _random_day(rng, date(2026, 8, 1), DOS_START - timedelta(days=1))
            start = end - timedelta(days=rng.choice([30, 60, 90]))
            kind = "EXPIRED"
        else:
            start = _random_day(rng, date(2026, 9, 15), date(2026, 11, 30))
            end = start + timedelta(days=rng.choice([60, 90]))
            kind = "VALID"
        if kind == "VALID" and roll < AUTH_EXPIRED_SHARE + AUTH_WRONG_CODE_SHARE:
            policy = curated.policies[entry.policy_id] if entry.policy_id else None
            others = [c for c in (policy.procedure_codes if policy else ()) if c != code]
            if others:
                code = rng.choice(others)  # authorized a different code than the one billed later
                kind = "WRONG_CODE"
        kinds[kind] += 1
        auths.append(
            {
                "auth_number": f"AUTH-2026-{number:05d}",
                "member_id": member["member_id"],
                "provider_npi": provider["npi"],
                "procedure_code": code,
                "start_date": start,
                "end_date": end,
                "units_approved": None,
            }
        )
    return auths, kinds


def _other_coverage(rng: random.Random, members: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chosen = rng.sample([m for m in members if _active_in_window(m)], OTHER_COVERAGE_COUNT)
    return [
        {
            "id": number,
            "member_id": member["member_id"],
            "payer_name": rng.choice(OTHER_PAYERS),
            "policy_number": f"OP{rng.randint(10_000_000, 99_999_999)}",
            "is_primary": True,
            "coverage_start": date(2026, 1, 1),
            "coverage_end": None,
        }
        for number, member in enumerate(chosen, start=1)
    ]


def _accumulators(
    rng: random.Random, curated: CuratedData, members: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], Counter[str]]:
    buckets: Counter[str] = Counter()
    rows = []
    for member in members:
        plan = curated.plans[member["plan_id"]]
        networks = [("IN_NETWORK", plan.in_network)]
        if plan.out_of_network is not None:
            networks.append(("OUT_OF_NETWORK", plan.out_of_network))
        for network, terms in networks:
            roll = rng.random()
            if network == "OUT_OF_NETWORK" and roll < 0.8:
                deductible, oop, bucket = 0, 0, "OON_NONE"
            elif roll < 0.30:
                deductible, oop, bucket = 0, 0, "NONE"
            elif roll < 0.50:
                deductible = terms.deductible_cents
                oop = min(terms.oop_max_cents, deductible + rng.randint(0, 150) * 100)
                bucket = "DEDUCTIBLE_MET"
            elif roll < 0.53:
                deductible = terms.deductible_cents
                oop = terms.oop_max_cents - rng.randint(0, 50) * 100
                bucket = "NEAR_OOP_MAX"
            else:
                deductible = rng.randint(0, terms.deductible_cents // 100) * 100
                oop = min(terms.oop_max_cents, deductible + rng.randint(0, 40) * 100)
                bucket = "PARTIAL"
            buckets[f"{network}:{bucket}"] += 1
            rows.append(
                {
                    "member_id": member["member_id"],
                    "period_start": PERIOD_START,
                    "network": network,
                    "period_end": PERIOD_END,
                    "deductible_met_cents": deductible,
                    "oop_met_cents": oop,
                }
            )
    return rows, buckets


def _visit_usage(
    rng: random.Random, curated: CuratedData, members: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    chosen = rng.sample([m for m in members if _active_in_window(m)], REHAB_USAGE_COUNT)
    rows = []
    for member in chosen:
        limit = curated.benefit(member["plan_id"], "REHAB_THERAPY").visit_limit or 1
        rows.append(
            {
                "member_id": member["member_id"],
                "period_start": PERIOD_START,
                "benefit_category": "REHAB_THERAPY",
                "visits_used": rng.randint(0, limit - 2),  # stays below the limit (no mapped code)
            }
        )
    return rows


def generate_reference(
    seed: int = DEFAULT_SEED, curated: CuratedData | None = None
) -> tuple[ReferenceData, dict[str, Any]]:
    """Return the reference tables and a distribution report."""
    curated = curated or load_curated()
    rng = random.Random(seed)
    fake = Faker("en_US")
    fake.seed_instance(seed)

    data = ReferenceData()
    data.members, coverage = _members(rng, fake)
    data.providers, data.provider_networks = _providers(rng, fake, curated)
    data.authorizations, auth_kinds = _authorizations(
        rng, curated, data.members, data.providers, data.provider_networks
    )
    data.other_coverage = _other_coverage(rng, data.members)
    data.accumulators, accumulator_buckets = _accumulators(rng, curated, data.members)
    data.visit_usage = _visit_usage(rng, curated, data.members)

    report = {
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        "counts": {name: len(rows) for name, rows in data.tables().items()},
        "members_by_plan": dict(sorted(Counter(m["plan_id"] for m in data.members).items())),
        "members_by_coverage": dict(sorted(coverage.items())),
        "providers_by_type": dict(Counter(p["provider_type"] for p in data.providers)),
        "providers_by_enrollment": dict(Counter(p["enrollment_status"] for p in data.providers)),
        "out_of_network_rows_by_plan": dict(
            sorted(
                Counter(n["plan_id"] for n in data.provider_networks if not n["in_network"]).items()
            )
        ),
        "authorizations_by_kind": dict(sorted(auth_kinds.items())),
        "accumulators_by_bucket": dict(sorted(accumulator_buckets.items())),
    }
    return data, report


def _report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Reference data distribution report",
        "",
        f"Generator `{report['generator_version']}`, seed {report['seed']}. All data synthetic.",
    ]
    for key, value in report.items():
        if isinstance(value, dict):
            lines += [
                "",
                f"## {key.replace('_', ' ').capitalize()}",
                "",
                "| Value | Count |",
                "|---|---|",
            ]
            lines += [f"| {k} | {v} |" for k, v in value.items()]
    return "\n".join(lines) + "\n"


def write_reference(out_dir: Path, seed: int = DEFAULT_SEED) -> dict[str, Any]:
    data, report = generate_reference(seed)
    for name, rows in data.tables().items():
        write_jsonl(out_dir / f"{name}.jsonl", rows)
    write_json(out_dir / "report.json", report)
    (out_dir / "report.md").write_text(_report_markdown(report), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", type=Path, default=GENERATED_DIR / "reference")
    args = parser.parse_args()
    report = write_reference(args.out, args.seed)
    print(f"wrote {args.out}: {report['counts']}")


if __name__ == "__main__":
    main()
