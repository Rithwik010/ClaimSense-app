"""Claim corpus generator (P3.4, INSTRUCTIONS.md §9.4): `IntakeClaim` JSON with a scenario tag and
expected outcomes, plus a digital PDF and a scanned-style image of every claim.

Claims that reach the model come straight from the scenario engine. Rule-failure claims start from
an engine claim and change one fact (unknown member, coverage ended, provider pending, late filing,
out of network, no referral, no or expired authorization, duplicate); claims whose every line is
denied by Group C come from the engine directly. Authorizations the claims rely on are written to
`authorizations_extra.jsonl` for the seed loader (P2.1).

    uv run python -m training.generate.claims [--seed N] [--out DIR] [--no-forms]
"""

import argparse
import random
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from app.db.curated import load_curated
from app.domain.contracts import IntakeClaim
from app.intake.form_codec import to_form_values
from app.rag.retrieve import Retriever
from training.generate.common import (
    DEFAULT_SEED,
    DOS_END,
    DOS_START,
    GENERATED_DIR,
    make_npi,
    write_json,
    write_jsonl,
)
from training.generate.forms import render_pdf, render_scan
from training.generate.reference import generate_reference
from training.generate.scenarios import GENERATOR_VERSION as SCENARIO_VERSION
from training.generate.scenarios import Scenario, ScenarioBuilder

GENERATOR_VERSION = "claims-v2"  # v2: criterion statuses, real retrieval

MODEL_PATH_MIX = {
    "approve_single": 30,
    "deny_dx": 12,
    "deny_criterion": 14,
    "deny_exclusion": 8,
    "pend_missing": 16,
    "office_visit": 10,
    "office_plus_procedure": 10,
    "office_same_day": 6,
    "same_profile_multi": 10,
    "two_policy": 8,
    "ncci_bypass": 8,
    "rule_denied_line": 8,
}
RULE_FAILURE_MIX = {
    "R04_member_not_found": 8,
    "R05_not_eligible": 10,
    "R06_enrollment_pending": 8,
    "R06_provider_not_found": 6,
    "R07_late_filing": 10,
    "R08_out_of_network": 10,
    "R09_missing_referral": 8,
    "R10_no_auth": 6,
    "R10_expired_auth": 6,
    "excluded_only": 6,
    "mue_only": 4,
    "DUP_duplicate": 4,
}
STATUS = {
    "PASS": "RECEIVED",
    "REJECT": "REJECTED",
    "DENY": "DENIED_BY_RULE",
    "PEND": "PENDED_BY_RULE",
}


def claim_decision(labels: list[dict[str, Any]]) -> str:
    decisions = {label["decision"] for label in labels}
    if "PEND" in decisions:
        return "PEND"
    if decisions == {"DENY"}:
        return "DENY"
    if decisions == {"APPROVE"}:
        return "APPROVE"
    return "PARTIAL"


class CorpusBuilder:
    def __init__(self, seed: int, retriever: Retriever | None = None) -> None:
        curated = load_curated()
        self.curated = curated
        self.rng = random.Random(seed)
        self.seed = seed
        self.reference = generate_reference(DEFAULT_SEED)[0]
        train = {p for p, x in curated.policies.items() if x.split == "TRAIN"}
        everything = set(curated.policies)
        self.builders = {
            "A": ScenarioBuilder(seed, "A", train, train, self.reference, retriever),
            "B": ScenarioBuilder(seed + 1, "B", everything, everything, self.reference, retriever),
        }
        self.members = self.reference.members
        self.providers = self.reference.providers
        self.network = {
            (n["npi"], n["plan_id"]): n["in_network"] for n in self.reference.provider_networks
        }
        self.npis = {p["npi"] for p in self.providers}
        self.counter = 0

    def _claim_id(self) -> str:
        self.counter += 1
        return f"CLM-C{self.counter:05d}"

    def _scenario(self, scenario_type: str, check: Any = None) -> Scenario:
        for _ in range(200):
            builder = self.builders["A" if self.rng.random() < 0.75 else "B"]
            scenario = builder.build(scenario_type, self._claim_id(), oon_rate=0.0)
            if check is None or check(scenario):
                return scenario
        raise RuntimeError(f"no {scenario_type} scenario passed the check")

    def _record(
        self,
        scenario: Scenario,
        scenario_type: str,
        claim: dict[str, Any] | None = None,
        outcome: str = "PASS",
        reason_codes: list[str] | None = None,
        authorizations: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        claim = claim or scenario.claim.model_dump(mode="json")
        IntakeClaim.model_validate(claim)
        expected: dict[str, Any] = {"rule_outcome": outcome, "status": STATUS[outcome]}
        if outcome == "PASS" or scenario_type in ("excluded_only", "mue_only"):
            expected["rule_outcome"] = scenario.rules.claim_outcome.value
            expected["status"] = STATUS[expected["rule_outcome"]]
            expected["line_labels"] = scenario.line_labels
            expected["claim_decision"] = claim_decision(scenario.line_labels)
            expected["reason_codes"] = sorted(
                {r for label in scenario.line_labels for r in label["reason_codes"]}
            )
            if scenario.target:
                expected["complexity"] = scenario.target.complexity.value
        else:
            expected["reason_codes"] = reason_codes or []
        return {
            "claim_id": claim["claim_id"],
            "scenario_type": scenario_type,
            "claim": claim,
            "expected": expected,
            "authorizations": scenario.authorizations if authorizations is None else authorizations,
            "metadata": {
                "generator_version": GENERATOR_VERSION,
                "scenario_version": SCENARIO_VERSION,
                "seed": self.seed,
                "scenario_type": scenario_type,
                "policy_id": scenario.policy_ids[0] if scenario.policy_ids else None,
                "policy_ids": scenario.policy_ids,
                "template_id": scenario.template_set,
                "plan_id": scenario.context.plan_id,
            },
        }

    # --- rule failures ---------------------------------------------------------------------------

    def _set_member(self, claim: dict[str, Any], member: dict[str, Any]) -> None:
        claim["member_id"] = member["member_id"]
        claim["patient"].update(
            first_name=member["first_name"],
            last_name=member["last_name"],
            date_of_birth=member["date_of_birth"].isoformat(),
            sex=member["sex"],
        )

    def _set_provider(self, claim: dict[str, Any], npi: str, tin: str) -> None:
        claim["billing_npi"], claim["billing_tin"] = npi, tin
        for line in claim["service_lines"]:
            line["rendering_npi"] = npi

    def _shift_dates(self, claim: dict[str, Any], first_day: date) -> None:
        days = [date.fromisoformat(line["date_of_service"]) for line in claim["service_lines"]]
        delta = first_day - min(days)
        for line, day in zip(claim["service_lines"], days, strict=True):
            line["date_of_service"] = (day + delta).isoformat()
        last = max(date.fromisoformat(line["date_of_service"]) for line in claim["service_lines"])
        claim["received_date"] = (last + timedelta(days=self.rng.randint(3, 15))).isoformat()

    def rule_failure(self, kind: str) -> list[dict[str, Any]]:
        rng = self.rng
        if kind in ("excluded_only", "mue_only"):
            scenario = self._scenario(kind)
            return [self._record(scenario, kind)]
        if kind == "DUP_duplicate":
            scenario = self._scenario("approve_single")
            original = self._record(scenario, "approve_single")
            duplicate = scenario.claim.model_dump(mode="json")
            duplicate["claim_id"] = self._claim_id()
            duplicate["received_date"] = (
                scenario.claim.received_date + timedelta(days=3)
            ).isoformat()
            return [
                original,
                self._record(scenario, kind, duplicate, "REJECT", ["RJ_DUPLICATE"], []),
            ]

        base_type, check = "office_visit", None
        if kind == "R08_out_of_network":
            check = lambda s: s.context.plan_id in ("PLN-HMO", "PLN-EPO")  # noqa: E731
        elif kind == "R09_missing_referral":
            base_type = "approve_single"
            check = lambda s: s.claim.referring_npi is not None  # noqa: E731
        elif kind.startswith("R10"):
            base_type = "approve_single"
            check = lambda s: bool(s.authorizations)  # noqa: E731
        scenario = self._scenario(base_type, check)
        claim = scenario.claim.model_dump(mode="json")
        plan_id = scenario.context.plan_id
        auths = scenario.authorizations

        if kind == "R04_member_not_found":
            claim["member_id"] = f"MBR-9{rng.randint(0, 99999):05d}"
            return [self._record(scenario, kind, claim, "REJECT", ["RJ_MEMBER_NOT_FOUND"])]
        if kind == "R05_not_eligible":
            options = [
                m
                for m in self.members
                if m["plan_id"] == plan_id
                and (
                    (
                        m["coverage_end"]
                        and DOS_START <= m["coverage_end"] < DOS_END - timedelta(days=3)
                    )
                    or DOS_START < m["coverage_start"] <= DOS_END
                )
            ]
            member = rng.choice(options)
            self._set_member(claim, member)
            if member["coverage_end"] and member["coverage_end"] < DOS_END:
                first = member["coverage_end"] + timedelta(days=rng.randint(1, 3))
            else:
                first = member["coverage_start"] - timedelta(days=rng.randint(1, 20))
            self._shift_dates(claim, first)
            return [self._record(scenario, kind, claim, "DENY", ["DN_NOT_ELIGIBLE"])]
        if kind == "R06_enrollment_pending":
            referral_types = self.curated.plans[plan_id].referral_required_provider_types
            options = [
                p
                for p in self.providers
                if p["enrollment_status"] == "PENDING"
                and self.network.get((p["npi"], plan_id))
                and p["provider_type"] not in referral_types
            ]
            if not options:
                return self.rule_failure(kind)
            provider = rng.choice(options)
            self._set_provider(claim, provider["npi"], provider["tin"])
            return [self._record(scenario, kind, claim, "PEND", ["PD_PROVIDER_ENROLLMENT"])]
        if kind == "R06_provider_not_found":
            npi = make_npi(rng, set(self.npis))
            self._set_provider(claim, npi, claim["billing_tin"])
            return [self._record(scenario, kind, claim, "REJECT", ["RJ_PROVIDER_NOT_FOUND"])]
        if kind == "R07_late_filing":
            window = self.curated.plans[plan_id].filing_window_inn_days
            last = max(
                date.fromisoformat(line["date_of_service"]) for line in claim["service_lines"]
            )
            claim["received_date"] = (
                last + timedelta(days=window + rng.randint(1, 40))
            ).isoformat()
            return [self._record(scenario, kind, claim, "DENY", ["DN_LATE_FILING"])]
        if kind == "R08_out_of_network":
            provider_type = scenario.provider["provider_type"]
            options = [
                p
                for p in self.providers
                if p["provider_type"] == provider_type
                and p["enrollment_status"] == "ENROLLED"
                and not self.network.get((p["npi"], plan_id))
            ]
            if not options:
                return self.rule_failure(kind)
            provider = rng.choice(options)
            self._set_provider(claim, provider["npi"], provider["tin"])
            return [self._record(scenario, kind, claim, "DENY", ["DN_OUT_OF_NETWORK"])]
        if kind == "R09_missing_referral":
            claim["referring_npi"] = None
            return [self._record(scenario, kind, claim, "DENY", ["DN_MISSING_REFERRAL"])]
        if kind == "R10_no_auth":
            claim["prior_auth_number"] = None
            return [self._record(scenario, kind, claim, "DENY", ["DN_NO_AUTH"], [])]
        if kind == "R10_expired_auth":
            first = min(
                date.fromisoformat(line["date_of_service"]) for line in claim["service_lines"]
            )
            end = first - timedelta(days=rng.randint(3, 30))
            expired = [
                {**a, "start_date": end - timedelta(days=90), "end_date": end} for a in auths
            ]
            return [self._record(scenario, kind, claim, "DENY", ["DN_NO_AUTH"], expired)]
        raise ValueError(kind)

    def build(self) -> list[dict[str, Any]]:
        records = []
        for scenario_type, count in MODEL_PATH_MIX.items():
            for _ in range(count):
                records.append(self._record(self._scenario(scenario_type), scenario_type))
        for kind, count in RULE_FAILURE_MIX.items():
            for _ in range(count):
                records.extend(self.rule_failure(kind))
        return records


def write_forms(records: list[dict[str, Any]], out_dir: Path, seed: int) -> None:
    forms = out_dir / "forms"
    forms.mkdir(parents=True, exist_ok=True)
    for count, record in enumerate(records, start=1):
        if count % 25 == 0 or count == len(records):
            print(f"forms: {count}/{len(records)}", flush=True)
        claim = IntakeClaim.model_validate(record["claim"])
        values = to_form_values(claim)
        (forms / f"{claim.claim_id}.pdf").write_bytes(render_pdf(values))
        rng = random.Random(f"{seed}-{claim.claim_id}")
        scan = render_scan(values, rng)
        pages = []
        for number, page in enumerate(scan.pages, start=1):
            name = f"{claim.claim_id}_scan_p{number}.jpg"
            page.save(forms / name, format="JPEG", quality=scan.noise["visual"]["jpeg_quality"])
            pages.append(name)
        record["forms"] = {
            "digital_pdf": f"{claim.claim_id}.pdf",
            "scan_pages": pages,
            "scan_noise": scan.noise,
            "scan_values": scan.values,
            # A missing or mistyped box makes the scanned copy a REJECT (R01, or H5 on R02/R03).
            "scan_expected_rule_outcome": "REJECT"
            if "value" in scan.noise
            else record["expected"]["rule_outcome"],
        }


def write_corpus(
    out_dir: Path,
    seed: int = DEFAULT_SEED,
    forms: bool = True,
    retriever: Retriever | None = None,
    retrieval: str = "simulated",
) -> dict[str, Any]:
    records = CorpusBuilder(seed, retriever).build()
    if forms:
        write_forms(records, out_dir, seed)
    auths = [a for r in records for a in r["authorizations"]]
    write_jsonl(out_dir / "claims.jsonl", records)
    write_jsonl(out_dir / "authorizations_extra.jsonl", auths)
    report = {
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        "retrieval": retrieval,
        "claims": len(records),
        "authorizations_extra": len(auths),
        "by_scenario": {},
        "by_rule_outcome": {},
        "by_claim_decision": {},
        "scans_with_value_noise": sum(
            1 for r in records if "value" in r.get("forms", {}).get("scan_noise", {})
        ),
    }
    for record in records:
        for key, value in (
            ("by_scenario", record["scenario_type"]),
            ("by_rule_outcome", record["expected"]["rule_outcome"]),
            ("by_claim_decision", record["expected"].get("claim_decision", "-")),
        ):
            report[key][value] = report[key].get(value, 0) + 1
    write_json(out_dir / "report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", type=Path, default=GENERATED_DIR / "claims")
    parser.add_argument("--no-forms", action="store_true")
    parser.add_argument("--simulated-retrieval", action="store_true", help="no Qdrant (tests)")
    args = parser.parse_args()
    retriever, retrieval = None, "simulated"
    if not args.simulated_retrieval:
        from training.generate.decision_dataset import live_retriever

        retriever, retrieval = live_retriever()
    report = write_corpus(args.out, args.seed, not args.no_forms, retriever, retrieval)
    print(f"wrote {report['claims']} claims to {args.out}")
    print({k: v for k, v in report.items() if k.startswith("by_")})


if __name__ == "__main__":
    main()
