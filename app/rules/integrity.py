"""Group A (data integrity): R01 to R04 and the duplicate check (§8.3). Any failure rejects the
claim (D8).

The claim arrives as received (a dict), so the contract's validation errors become rule failures
(A-R8): a missing or empty field → R01, a code with the wrong format → R02, an NPI with the wrong
format or check digit → R03. Any other validation error is not a rule failure: intake validates
claims before the rules run, so `InvalidClaimData` is raised (P2.3a decision 1).
"""

from collections.abc import Mapping
from datetime import date
from typing import Any

from pydantic import ValidationError

from app.domain.contracts import IntakeClaim, RuleOutcomeValue, RuleResult
from app.rules.reference import MissingReference, RulesReference
from app.rules.results import failed, line_fields, passed

NPI_FIELDS = ("billing_npi", "referring_npi", "rendering_npi")
CODE_FIELDS = ("diagnoses", "procedure_code", "place_of_service", "modifiers")
DUPLICATE_IGNORED_STATUS = "REJECTED"  # A-R6


class InvalidClaimData(ValueError):
    """A validation error that A-R8 does not map to R01, R02 or R03."""


def icd10_fiscal_year(day: date) -> int:
    """ICD-10-CM fiscal years start on 1 October (FY2027 = 2026-10-01 to 2027-09-30)."""
    return day.year + 1 if day.month >= 10 else day.year


def _line_count(data: Mapping[str, Any]) -> int:
    lines = data.get("service_lines")
    return len(lines) if isinstance(lines, list) else 0


def _r02_fields(line_count: int) -> list[str]:
    return ["diagnoses"] + line_fields(
        line_count, "procedure_code", "place_of_service", "modifiers", "date_of_service"
    )


def _r03_fields(line_count: int) -> list[str]:
    return ["billing_npi", *line_fields(line_count, "rendering_npi"), "referring_npi"]


def _contract_rule(error: Mapping[str, Any]) -> str | None:
    """The rule a validation error belongs to (A-R8), or None when it belongs to none."""
    names = [part for part in error["loc"] if isinstance(part, str)]
    value = error.get("input")
    blank = value is None or value == [] or (isinstance(value, str) and not value.strip())
    if error["type"] == "missing" or blank:
        return "R01"
    if names and names[-1] in NPI_FIELDS:
        return "R03"
    if names and names[-1] in CODE_FIELDS and error["type"] == "string_pattern_mismatch":
        return "R02"
    return None


def _path(error: Mapping[str, Any]) -> str:
    return ".".join(str(part) for part in error["loc"])


def contract_failures(data: Mapping[str, Any]) -> tuple[IntakeClaim | None, list[RuleResult]]:
    """Validate the claim. Returns the claim, or None with its R01/R02/R03 failures."""
    try:
        return IntakeClaim.model_validate(data), []
    except ValidationError as error:
        errors = error.errors()
    by_rule: dict[str, list[str]] = {}
    for item in errors:
        rule = _contract_rule(item)
        if rule is None:
            raise InvalidClaimData(f"{_path(item)}: {item['msg']}") from None
        by_rule.setdefault(rule, []).append(_path(item))
    lines = _line_count(data)
    results = []
    if "R01" in by_rule:
        missing = by_rule["R01"]
        results.append(
            failed(
                "R01",
                RuleOutcomeValue.REJECT,
                "RJ_MISSING_FIELD",
                f"Required field missing: {', '.join(missing)}.",
                missing,
            )
        )
    if "R02" in by_rule:
        results.append(
            failed(
                "R02",
                RuleOutcomeValue.REJECT,
                "RJ_INVALID_CODE",
                f"Code with an invalid format: {', '.join(by_rule['R02'])}.",
                _r02_fields(lines),
            )
        )
    if "R03" in by_rule:
        results.append(
            failed(
                "R03",
                RuleOutcomeValue.REJECT,
                "RJ_INVALID_NPI",
                f"NPI not 10 digits with a valid check digit: {', '.join(by_rule['R03'])}.",
                _r03_fields(lines),
            )
        )
    return None, results


def check_codes(claim: IntakeClaim, reference: RulesReference) -> RuleResult:
    """R02 on a claim whose codes have a valid format: every diagnosis is a billable ICD-10-CM code
    in the fiscal year of every date of service, every procedure code is in the code table, and
    every place of service is an assigned code."""
    problems = []
    for year in sorted({icd10_fiscal_year(line.date_of_service) for line in claim.service_lines}):
        if year not in reference.icd10_codes:
            raise MissingReference(f"ICD-10-CM FY{year}")
        valid = reference.icd10_codes[year]
        problems += [
            f"diagnosis {code} (FY{year})" for code in claim.diagnoses if code not in valid
        ]
    for line in claim.service_lines:
        if line.procedure_code not in reference.procedure_codes:
            problems.append(f"line {line.line_no} procedure code {line.procedure_code}")
        if line.place_of_service not in reference.place_of_service_codes:
            problems.append(f"line {line.line_no} place of service {line.place_of_service}")
    fields = _r02_fields(len(claim.service_lines))
    if problems:
        return failed(
            "R02",
            RuleOutcomeValue.REJECT,
            "RJ_INVALID_CODE",
            f"Not a valid code: {'; '.join(problems)}.",
            fields,
        )
    return passed("R02", "Every diagnosis, procedure and place-of-service code is valid.", fields)


def check_member(member_id: str, reference: RulesReference) -> RuleResult:
    """R04: the member ID is on file."""
    if member_id in reference.members:
        return passed("R04", f"Member {member_id} found.", ["member_id"])
    return failed(
        "R04",
        RuleOutcomeValue.REJECT,
        "RJ_MEMBER_NOT_FOUND",
        f"Member {member_id} not found.",
        ["member_id"],
    )


def check_duplicate(claim: IntakeClaim, reference: RulesReference) -> RuleResult:
    """Duplicate: a line with the same member, billing NPI, date of service and procedure code as
    a line of another claim on file that was not rejected (A-R6)."""
    matches = []
    for line in claim.service_lines:
        for existing in reference.existing_claims:
            if (
                existing.claim_id != claim.claim_id
                and existing.status != DUPLICATE_IGNORED_STATUS
                and existing.member_id == claim.member_id
                and existing.billing_npi == claim.billing_npi
                and existing.date_of_service == line.date_of_service
                and existing.procedure_code == line.procedure_code
            ):
                matches.append(f"line {line.line_no} repeats claim {existing.claim_id}")
    fields = [
        "member_id",
        "billing_npi",
        *line_fields(len(claim.service_lines), "date_of_service", "procedure_code"),
    ]
    if matches:
        return failed(
            "DUP",
            RuleOutcomeValue.REJECT,
            "RJ_DUPLICATE",
            f"Duplicate of a claim on file: {'; '.join(matches)}.",
            fields,
        )
    return passed("DUP", "No claim on file has the same member, provider, date and code.", fields)


def check_group_a(
    data: Mapping[str, Any], reference: RulesReference
) -> tuple[IntakeClaim | None, list[RuleResult]]:
    """Every Group A check that can run (A-R7), in order R01, R02, R03, R04, DUP. On a claim that
    fails the contract, only R04 can still run (when the member ID is there)."""
    claim, results = contract_failures(data)
    if claim is None:
        member_id = data.get("member_id")
        if isinstance(member_id, str) and member_id.strip():
            results.append(check_member(member_id, reference))
        return None, results
    lines = len(claim.service_lines)
    return claim, [
        passed("R01", "Every required field is present.", []),
        check_codes(claim, reference),
        passed("R03", "Every NPI has a valid check digit.", _r03_fields(lines)),
        check_member(claim.member_id, reference),
        check_duplicate(claim, reference),
    ]
