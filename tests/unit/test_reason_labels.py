"""Every internal reason code is listed everywhere reason codes are listed: the CARC/RARC map
(`data/curated/reason_code_map.csv`), the explanation's plain-language labels
(`app/explain/render.py`) and the web app's (`frontend-web/src/lib/labels.ts`); and every reason a
rule can give is in the map (§8.3, D-CARC-2, D-CARC-3)."""

import re
from pathlib import Path

from app.db.curated import load_curated
from app.domain.contracts import LineDecision
from app.explain.render import REASON_LABELS
from app.ml.derive import DENY_CRITERION, DENY_EXCLUSION, PEND_MISSING
from app.review.actions import OVERRIDE_REASONS
from app.rules.line_edits import RULE_OF

ROOT = Path(__file__).resolve().parents[2]
LABELS_TS = ROOT / "frontend-web" / "src" / "lib" / "labels.ts"
GROUP_A_B_CODES = {
    "RJ_MISSING_FIELD",
    "RJ_INVALID_CODE",
    "RJ_INVALID_NPI",
    "RJ_MEMBER_NOT_FOUND",
    "RJ_PROVIDER_NOT_FOUND",
    "RJ_DUPLICATE",
    "RJ_LOW_CONFIDENCE_FIELD",
    "DN_NOT_ELIGIBLE",
    "DN_LATE_FILING",
    "DN_OUT_OF_NETWORK",
    "DN_MISSING_REFERRAL",
    "DN_NO_AUTH",
    "PD_PROVIDER_ENROLLMENT",
}


def web_labels(name: str) -> dict[str, str]:
    """The `export const <name>: Record<string, string> = {...}` object of labels.ts."""
    text = LABELS_TS.read_text(encoding="utf-8")
    body = re.search(rf"export const {name}\b[^=]*=\s*\{{(.*?)\n\}};", text, re.S)
    assert body, name
    return dict(re.findall(r'^\s*(\w+):\s*"([^"]*)",?$', body.group(1), re.M))


def test_the_map_and_both_label_tables_list_the_same_codes() -> None:
    mapped = set(load_curated().reason_codes)

    assert set(REASON_LABELS) == mapped
    assert web_labels("REASONS") == {code: REASON_LABELS[code] for code in mapped}


def test_every_rule_reason_is_mapped() -> None:
    assert set(RULE_OF) | GROUP_A_B_CODES <= set(load_curated().reason_codes)
    assert RULE_OF["DN_VISIT_LIMIT"] == "R21"


# --- Reviewer override reasons (D-REV-9) ----------------------------------------------------------


def test_the_override_reasons_are_the_mapped_line_reasons() -> None:
    """DENY: every line-level denial code (the model's and the line rules') with an approved CARC;
    PEND: the pend reasons, without the internal MODEL_OUTPUT_INVALID."""
    mapped = load_curated().reason_codes
    deny, pend = OVERRIDE_REASONS[LineDecision.DENY], OVERRIDE_REASONS[LineDecision.PEND]

    assert set(deny) == {DENY_CRITERION, DENY_EXCLUSION} | set(RULE_OF)
    assert all(mapped[c].outcome == "DENY" and mapped[c].carc for c in deny)
    assert set(pend) == {c for c, e in mapped.items() if e.outcome == "PEND"} - {
        "MODEL_OUTPUT_INVALID"
    }
    assert PEND_MISSING in pend


def test_the_web_app_offers_the_same_override_reasons() -> None:
    text = LABELS_TS.read_text(encoding="utf-8")
    block = re.search(r"export const OVERRIDE_REASONS\b.*?\n\};", text, re.S)
    assert block
    lists = {
        name: re.findall(r'"([A-Z_]+)"', codes)
        for name, codes in re.findall(r"(DENY|PEND): \[(.*?)\]", block.group(0), re.S)
    }

    assert lists == {d.value: list(codes) for d, codes in OVERRIDE_REASONS.items()}
