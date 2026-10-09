"""Task P2.3b: the impact of rules v2 (R14 to R20), written independently of app/rules.

Report only. The checks follow the definitions the team approved on 2026-10-09 (D-RULE-2 to
D-RULE-4; the plan's first versions are in commit 37ab24f) and run over:

- the 90 golden rules cases and the 30 golden end-to-end claims: every case a check would change,
  with the H5 conversion where a check reads a field below the confidence threshold;
- the 2,600 records of the model v1 decision dataset: the lines each check catches, by split and by
  the line's current label (metadata `line_labels`), compared with the V1a numbers (PROGRESS_LOG.md
  2026-09-24: 391 diagnosis-mismatch lines; R14 on 32 ESI lines, 20 of them becoming DENY).

It also prints the code facts the plan cites (MUE limits, add-on status, NCCI pairs) and the
official text of the candidate CARC and RARC codes. Codes, limits, indicators and ICD-10-CM,
HCPCS Level II, CARC and RARC text only: no AMA CPT descriptor text is read out or written (H10).

    uv run python -m scripts.verify.rules_v2_impact
    # prints the report and writes data/generated/verification/rules_v2_impact.md
"""

import csv
import html
import io
import json
import re
import zipfile
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from app.db import raw
from app.db.curated import CuratedData, load_curated
from scripts.verify.rules_fixture import load_cases

ROOT = Path(__file__).resolve().parents[2]
DECISION_DIR = ROOT / "data" / "generated" / "decision"
E2E_CASES = ROOT / "tests" / "golden" / "e2e" / "cases.json"
OUT = ROOT / "data" / "generated" / "verification" / "rules_v2_impact.md"
CARC_HTML = raw.RAW_DIR / "carc-rarc" / "2026-09-21" / "Claim Adjustment Reason Codes _ X12.html"
RARC_HTML = raw.RAW_DIR / "carc-rarc" / "2026-09-21" / "Remittance Advice Remark Codes _ X12.html"
SPLITS = ("train", "validation", "test")
CONFIDENCE_MIN = 0.85  # A-R9
FACT_DAY = date(2026, 11, 1)  # a day inside the R1 window for NCCI activity

# --- Proposed code roles (the plan's data/curated/rule_code_roles.csv) --------------------------
# Roles come from the billing articles' CPT lists (article_x_hcpc_code) and the PFS RVU26A file
# (global days ZZZ = add-on code; the descriptor is read to assign the role, never copied).

ESI = {"62321", "62323", "64479", "64483"}  # A56651 CPT group 1, primary codes
ESI_ADDON = {"64480", "64484"}  # A56651 CPT group 1, PFS global ZZZ
INTERLAMINAR = {"62321", "62323"}  # interlaminar or caudal ESI
TRANSFORAMINAL = {"64479": "64480", "64483": "64484"}  # primary -> its additional-level add-on
FACET_INJECTION = {"64490", "64493"}  # A57787 CPT group 1, primary injection codes
FACET_ADDON = {"64491", "64494"}  # A57787 CPT group 1, PFS global ZZZ
FACET_THIRD_LEVEL = {"64492", "64495"}  # A57787 CPT group 2: "non-covered"
RADIOFREQUENCY = {"64633", "64634", "64635", "64636"}  # A57787 CPT group 1, denervation
CERVICAL_THORACIC = {"64490", "64491", "64492", "64633", "64634"}
LUMBAR_SACRAL = {"64493", "64494", "64495", "64635", "64636"}
HOME_SLEEP_TEST = {"95800", "95801", "95806", "G0398", "G0399", "G0400"}  # A56923 CPT group 1
NERVE_CONDUCTION = {"95907", "95908", "95909", "95910", "95911", "95912", "95913"}  # A57478
NEEDLE_EMG = {
    "95860", "95861", "95863", "95864", "95865", "95866", "95867", "95868", "95869", "95870",
    "95872", "95885", "95886", "95887",
}  # A57478 CPT group 1  # fmt: skip
TESTING_MINUTES = {"96130": 60, "96131": 60, "96136": 30}  # in-scope testing codes, per unit

# --- Proposed diagnosis sets ------------------------------------------------------------------

PARASOMNIA = {"G4750", "G4751", "G4752", "G4753", "G4754", "G4759"}  # G47.50-G47.59 (Q5)
GROUP_1_ONLY = {"66982"}  # A56544: group 2 is reported "if applicable" (Q6)
CARPAL_TUNNEL = {"G5600", "G5601", "G5602", "G5603"}  # the L34594 exception (report only)
SYNOVIAL_CYST = {"M7130", "M7138"}  # M71.3 other bursal cyst, covered by A57787 (to confirm)
FOOT_CLASS_MODIFIERS = {"Q7", "Q8", "Q9"}  # A57188 group 2 "only with modifier Q7, Q8, or Q9"
VEINS = {"36475", "36478", "37765"}  # SURG-003.F4: ablation and stab phlebectomy
IMAGING = {"70450", "70551", "70553", "72141"}  # IMG-001.F2: the in-scope imaging codes
D_GOLD_1 = {"R11-02", "R11-03", "R11-07", "R11-08", "X-02"}  # their L97419 becomes REPLACEMENT
REPLACEMENT = {"L97419": "L97412"}  # proposed: a code of A58565 group 1 (D-GOLD-1)


# --- Checks -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Hit:
    rule: str
    line_no: int
    outcome: str  # DENY | FLAG
    reason: str  # internal reason code (DENY) or flag (FLAG)
    fields: tuple[str, ...]
    detail: str


@dataclass(frozen=True)
class Line:
    index: int
    line_no: int
    code: str
    day: str
    units: int
    modifiers: tuple[str, ...]
    diagnoses: tuple[str, ...]  # the line's own, through its pointers, in pointer order
    pointer_indexes: tuple[int, ...]


def lines_of(claim: Mapping[str, Any]) -> list[Line]:
    diagnoses = claim.get("diagnoses") or []
    out = []
    for i, s in enumerate(claim.get("service_lines") or []):
        indexes = tuple(
            ord(p) - ord("A")
            for p in s.get("diagnosis_pointers") or []
            if isinstance(p, str) and len(p) == 1 and 0 <= ord(p) - ord("A") < len(diagnoses)
        )
        out.append(
            Line(
                i,
                s.get("line_no", i + 1),
                s.get("procedure_code") or "",
                str(s.get("date_of_service")),
                int(s.get("units") or 0),
                tuple(s.get("modifiers") or []),
                tuple(diagnoses[k] for k in indexes),
                indexes,
            )
        )
    return out


def _dx_fields(line: Line) -> tuple[str, ...]:
    return (
        f"service_lines.{line.index}.procedure_code",
        f"service_lines.{line.index}.diagnosis_pointers",
        *(f"diagnoses.{k}" for k in line.pointer_indexes),
    )


def _day_fields(lines: Iterable[Line], *names: str) -> tuple[str, ...]:
    return tuple(f"service_lines.{x.index}.{n}" for x in lines for n in names)


@dataclass(frozen=True)
class Lookups:
    curated: CuratedData
    covered: Mapping[str, Mapping[int, frozenset[str]]]  # article -> group -> codes


def r15_supported(line: Line, lookups: Lookups, exact: bool) -> bool | None:
    """None: the code has no billing article (not checked). `exact` (approved, Q6 and Q7) follows
    the article where the v1 group sets differ: 66982 needs group 1 only; A56456's group 2A must
    be the line's first diagnosis; A57188's group 2 counts with modifier Q7, Q8 or Q9. Without it:
    the v1 group sets (generator, V1a)."""
    support = lookups.curated.diagnosis_support.get(line.code)
    if support is None:
        return None
    groups = lookups.covered.get(support.billing_article, {})

    def has(group: int, among: Sequence[str]) -> bool:
        return any(dx in groups.get(group, frozenset()) for dx in among)

    alternatives = list(support.alternatives)
    if exact and line.code in GROUP_1_ONLY:
        alternatives = [(1,)]
    if exact and support.billing_article == "A57188" and FOOT_CLASS_MODIFIERS & set(line.modifiers):
        alternatives.append((2,))
    for alternative in alternatives:
        if exact and support.billing_article == "A56456" and alternative == (2, 3):
            if line.diagnoses and has(2, line.diagnoses[:1]) and has(3, line.diagnoses[1:]):
                return True
            continue
        if all(has(group, line.diagnoses) for group in alternative):
            return True
    return False


def check_r15(lines: list[Line], lookups: Lookups, exact: bool = True) -> list[Hit]:
    return [
        Hit(
            "R15",
            x.line_no,
            "DENY",
            "DN_DX_NOT_SUPPORTED",
            _dx_fields(x),
            f"{x.code}: no supporting diagnosis among {list(x.diagnoses)}",
        )
        for x in lines
        if r15_supported(x, lookups, exact) is False
    ]


def check_r14(lines: list[Line]) -> list[Hit]:
    """An ESI line is denied when another block (another ESI code or a facet joint injection) is
    billed on the same date; add-on codes, radiofrequency denervation and the same code on another
    line (bilateral use) are not other blocks; a facet line for a synovial cyst is the exception."""
    hits = []
    for x in lines:
        if x.code not in ESI:
            continue
        same_day = [y for y in lines if y.day == x.day and y.index != x.index]
        others = [y for y in same_day if y.code in ESI | FACET_INJECTION and y.code != x.code]
        blocking = [
            y
            for y in others
            if not (y.code in FACET_INJECTION and SYNOVIAL_CYST & set(y.diagnoses))
        ]
        if blocking:
            fields = _day_fields([x, *others], "procedure_code", "date_of_service")
            fields += tuple(f for y in others if y.code in FACET_INJECTION for f in _dx_fields(y))
            hits.append(
                Hit(
                    "R14",
                    x.line_no,
                    "DENY",
                    "DN_MULTIPLE_BLOCKS",
                    fields,
                    f"{x.code} with {[y.code for y in blocking]} on {x.day}",
                )
            )
    return hits


def check_r16(lines: list[Line], parasomnia: set[str] = PARASOMNIA) -> list[Hit]:
    return [
        Hit(
            "R16",
            x.line_no,
            "DENY",
            "DN_HOME_TEST_PARASOMNIA",
            _dx_fields(x),
            f"{x.code} with {sorted(parasomnia & set(x.diagnoses))}",
        )
        for x in lines
        if x.code in HOME_SLEEP_TEST and parasomnia & set(x.diagnoses)
    ]


def check_r17(lines: list[Line]) -> list[Hit]:
    """L34594 says "usually" (D-RULE-2): a flag on every nerve conduction line with no needle EMG
    line anywhere on the claim, carpal tunnel included."""
    if any(y.code in NEEDLE_EMG for y in lines):
        return []
    fields = _day_fields(lines, "procedure_code")
    return [
        Hit("R17", x.line_no, "FLAG", "NCS_WITHOUT_EMG", fields, x.code)
        for x in lines
        if x.code in NERVE_CONDUCTION
    ]


def sides(line: Line) -> set[str]:
    """RT or LT alone: that side; modifier 50, both or neither: both sides (the R18 fix)."""
    side = {"RT", "LT"} & set(line.modifiers)
    return side if len(side) == 1 and "50" not in line.modifiers else {"RT", "LT"}


def check_r18(lines: list[Line]) -> list[Hit]:
    hits = []
    for primary, addon in TRANSFORAMINAL.items():
        for day in sorted({x.day for x in lines if x.code in (primary, addon)}):
            group = [x for x in lines if x.day == day and x.code in (primary, addon)]
            levels = {s: sum(x.units for x in group if s in sides(x)) for s in ("RT", "LT")}
            over = {s for s, n in levels.items() if n > 2}
            for x in group:
                if x.code == addon and sides(x) & over:
                    names = ("procedure_code", "units", "modifiers", "date_of_service")
                    detail = f"right {levels['RT']} levels, left {levels['LT']}"
                    fields = _day_fields(group, *names)
                    hits.append(Hit("R18", x.line_no, "DENY", "DN_ESI_LEVELS", fields, detail))
    for x in lines:
        if x.code in INTERLAMINAR and "50" in x.modifiers:
            fields = _day_fields([x], "procedure_code", "modifiers")
            hits.append(Hit("R18", x.line_no, "DENY", "DN_ESI_LEVELS", fields, "bilateral"))
    return hits


def check_r19(lines: list[Line]) -> list[Hit]:
    hits = [
        Hit(
            "R19",
            x.line_no,
            "DENY",
            "DN_FACET_LEVELS",
            _day_fields([x], "procedure_code"),
            f"{x.code} third level",
        )
        for x in lines
        if x.code in FACET_THIRD_LEVEL
    ]
    for day in {x.day for x in lines}:
        regions = [
            {x.code for x in lines if x.day == day} & region
            for region in (CERVICAL_THORACIC, LUMBAR_SACRAL)
        ]
        if all(regions):
            for x in lines:
                if x.day == day and x.code in CERVICAL_THORACIC | LUMBAR_SACRAL:
                    fields = _day_fields(lines, "procedure_code", "date_of_service")
                    hits.append(Hit("R19", x.line_no, "FLAG", "FACET_TWO_REGIONS", fields, day))
    return hits


def check_r20(lines: list[Line]) -> list[Hit]:
    minutes = sum(x.units * TESTING_MINUTES[x.code] for x in lines if x.code in TESTING_MINUTES)
    if minutes <= 8 * 60:
        return []
    return [
        Hit(
            "R20",
            x.line_no,
            "FLAG",
            "EXTENDED_TESTING",
            _day_fields(lines, "procedure_code", "units"),
            f"{minutes} minutes",
        )
        for x in lines
        if x.code in TESTING_MINUTES
    ]


def proposed(claim: Mapping[str, Any], lookups: Lookups) -> list[Hit]:
    """Every check with its approved definition, in rule order."""
    lines = lines_of(claim)
    return [
        *check_r14(lines),
        *check_r15(lines, lookups),
        *check_r16(lines),
        *check_r17(lines),
        *check_r18(lines),
        *check_r19(lines),
        *check_r20(lines),
    ]


# --- Sources ------------------------------------------------------------------------------------


def load_lookups() -> Lookups:
    curated = load_curated()
    articles = raw.read_article_diagnoses(
        {s.billing_article for s in curated.diagnosis_support.values()}
    )
    return Lookups(curated, {a: d.covered for a, d in articles.items()})


def x12_codes(path: Path) -> dict[str, tuple[str, str]]:
    """Code -> (current | deactivated, official description) from an X12 code list page."""
    text = path.read_text(encoding="utf-8")
    row = re.compile(
        r'<tr class="prod-set (\w+)"><td class="code">([^<]+)</td>'
        r'<td class="description">(.*?)<span class="dates">',
        re.DOTALL,
    )
    out = {}
    for status, code, body in row.findall(text):
        clean = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", body))).strip()
        out[code.strip()] = (status, clean)
    return out


def pfs_global_days(codes: set[str]) -> dict[str, str]:
    """PFS RVU26A global days (ZZZ = add-on) of codes without a modifier; no descriptor read."""
    out = {}
    with raw.PFS_CSV.open(encoding="latin-1", newline="") as f:
        for row in csv.reader(f):
            if len(row) > 14 and row[0] in codes and not row[1].strip():
                out[row[0]] = row[14]
    return out


def article_cpt_groups(article_ids: set[str]) -> dict[str, dict[str, set[str]]]:
    numeric = {a.removeprefix("A") for a in article_ids}
    with zipfile.ZipFile(raw.MCD_ARTICLES_ZIP) as outer:
        inner = zipfile.ZipFile(io.BytesIO(outer.read("current_article_csv.zip")))

    def rows(name: str) -> Iterable[dict[str, str]]:
        with inner.open(name) as f:
            yield from csv.DictReader(io.TextIOWrapper(f, encoding="latin-1"))

    version = {r["article_id"]: r["article_version"] for r in rows("article.csv")}
    out: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for r in rows("article_x_hcpc_code.csv"):
        a = r["article_id"]
        if a in numeric and r["article_version"] == version[a]:
            out[f"A{a}"][r["hcpc_code_group"]].add(r["hcpc_code_id"])
    return out


# --- Golden cases and dataset -------------------------------------------------------------------


def low_confidence(hit: Hit, confidences: Mapping[str, float]) -> list[str]:
    return sorted(
        path
        for path, value in confidences.items()
        if value < CONFIDENCE_MIN and any(path == f or path.startswith(f"{f}.") for f in hit.fields)
    )


def golden_rules_changes(lookups: Lookups) -> list[str]:
    rows = []
    for case in load_cases():
        expected = case["expected"]
        if not expected.get("line_outcomes"):
            continue  # stops in Group A or B: Group C never runs
        hits = proposed(case["given"]["claim"], lookups)
        confidences = case["given"].get("field_confidences") or {}
        for h in hits:
            low = low_confidence(h, confidences)
            h5 = f"; H5: REJECT RJ_LOW_CONFIDENCE_FIELD ({', '.join(low)})" if low else ""
            rows.append(
                f"| {case['case_id']} | {h.line_no} | {h.rule} | {h.outcome} {h.reason} | "
                f"{h.detail}{h5} |"
            )
    return rows


def e2e_changes(lookups: Lookups) -> list[str]:
    rows = []
    for case in json.loads(E2E_CASES.read_text(encoding="utf-8"))["cases"]:
        rules = case["expected"]["rules"]
        if not rules.get("line_outcomes"):
            continue
        confidences = case["given"].get("field_confidences") or {}
        for h in proposed(case["given"]["claim"], lookups):
            low = low_confidence(h, confidences)
            h5 = f"; H5: REJECT ({', '.join(low)})" if low else ""
            rows.append(
                f"| {case['case_id']} | {h.line_no} | {h.rule} | {h.outcome} {h.reason} | "
                f"{h.detail}{h5} |"
            )
    return rows


@dataclass(frozen=True)
class Record:
    split: str
    record_id: str
    claim: Mapping[str, Any]
    labels: Mapping[int, str]  # line -> "MODEL APPROVE", "RULE DENY", ...
    scenario: str


def load_records() -> list[Record]:
    out = []
    for split in SPLITS:
        meta = {}
        with (DECISION_DIR / f"{split}.jsonl").open(encoding="utf-8") as f:
            for row in map(json.loads, f):
                meta[row["metadata"]["record_id"]] = row["metadata"]
        with (DECISION_DIR / f"{split}_inputs.jsonl").open(encoding="utf-8") as f:
            for row in map(json.loads, f):
                m = meta[row["record_id"]]
                labels = {x["line_no"]: f"{x['source']} {x['decision']}" for x in m["line_labels"]}
                out.append(
                    Record(split, row["record_id"], row["claim"], labels, m["scenario_type"])
                )
    return out


def dataset_table(
    records: Sequence[Record], check: Callable[[list[Line]], list[Hit]], name: str
) -> tuple[list[str], Counter[tuple[str, str]]]:
    counts: Counter[tuple[str, str]] = Counter()
    for r in records:
        for h in check(lines_of(r.claim)):
            counts[(r.split, f"{h.outcome} {h.reason} <- {r.labels.get(h.line_no, '?')}")] += 1
    rows = [
        f"| {name} | {what} | {counts[('train', what)]} | {counts[('validation', what)]} | "
        f"{counts[('test', what)]} | {sum(counts[(s, what)] for s in SPLITS)} |"
        for what in sorted({w for _, w in counts})
    ]
    return rows, counts


def main() -> None:
    lookups = load_lookups()
    out: list[str] = ["# P2.3b planning: impact of the proposed rules v2", ""]

    out += ["## Code facts", ""]
    family = (
        ESI | ESI_ADDON | FACET_INJECTION | FACET_ADDON | FACET_THIRD_LEVEL | RADIOFREQUENCY
        | HOME_SLEEP_TEST | NERVE_CONDUCTION | NEEDLE_EMG | set(TESTING_MINUTES) | VEINS | IMAGING
    )  # fmt: skip
    mue = raw.read_mue(family)
    days = pfs_global_days(family)
    out += ["| Code | MUE | PFS global days |", "|---|---|---|"]
    out += [
        f"| {c} | {mue[c].max_units if c in mue else '-'} | {days.get(c, '-')} |"
        for c in sorted(family)
    ]
    pairs = [p for p in raw.read_ncci_pairs(family) if p.active_on(FACT_DAY)]

    def pairs_between(a: set[str], b: set[str]) -> str:
        found = sorted(
            f"{p.column1}/{p.column2} ({p.modifier_indicator})"
            for p in pairs
            if (p.column1 in a and p.column2 in b) or (p.column1 in b and p.column2 in a)
        )
        return ", ".join(found) or "none"

    out += [
        "",
        f"NCCI pairs active on {FACT_DAY} (column 1/column 2 (modifier indicator)):",
        "",
        f"- ESI with facet injection: {pairs_between(ESI | ESI_ADDON, FACET_INJECTION)}",
        f"- ESI with ESI: {pairs_between(ESI | ESI_ADDON, ESI | ESI_ADDON)}",
        f"- radiofrequency with ESI: {pairs_between(RADIOFREQUENCY, ESI)}",
        f"- ablation (36475, 36478) with stab phlebectomy (37765): "
        f"{pairs_between(VEINS - {'37765'}, {'37765'})}",
        f"- imaging (70450, 70551, 70553, 72141): {pairs_between(IMAGING, IMAGING)}",
        f"- nerve conduction with nerve conduction: "
        f"{pairs_between(NERVE_CONDUCTION, NERVE_CONDUCTION)}",
        f"- extremity needle EMG (95860-95864) with 95869 or 95870: "
        f"{pairs_between({'95860', '95861', '95863', '95864'}, {'95869', '95870'})}",
        "",
    ]
    groups = article_cpt_groups({"A56651", "A57787", "A57478", "A56923"})
    out += ["Billing article CPT groups:", ""]
    out += [
        f"- {a} group {g}: {', '.join(sorted(codes))}"
        for a in sorted(groups)
        for g, codes in sorted(groups[a].items())
    ]
    icd = raw.read_icd10_codes()
    sets = {
        "parasomnia (G47.50-G47.59)": PARASOMNIA,
        "synovial cyst (M71.3, to confirm against the tabular)": SYNOVIAL_CYST,
    }
    out += ["", "Diagnosis sets (ICD-10-CM FY2027 titles):", ""]
    for name, codes in sets.items():
        a56923 = lookups.covered.get("A56923", {})
        a57787 = lookups.covered.get("A57787", {})
        out += [
            f"- {name}: "
            + "; ".join(
                f"{c} {icd.get(c, 'NOT IN FY2027')} "
                f"[A56923 groups {sorted(g for g, s in a56923.items() if c in s)}, "
                f"A57787 groups {sorted(g for g, s in a57787.items() if c in s)}]"
                for c in sorted(codes)
            )
        ]

    out += ["", "## CARC and RARC candidates (official text, data/raw/carc-rarc/2026-09-21)", ""]
    carc, rarc = x12_codes(CARC_HTML), x12_codes(RARC_HTML)
    for kind, table, codes in (
        ("CARC", carc, ("4", "11", "50", "58", "96", "151", "167", "236")),
        ("RARC", rarc, ("M76", "N115", "N130", "N362", "N386", "N657")),
    ):
        for code in codes:
            status, text = table.get(code, ("MISSING", ""))
            out.append(f"- {kind} {code} ({status}): {text}")

    out += ["", "## Golden rules cases (90): changes", ""]
    rows = golden_rules_changes(lookups)
    out += ["| Case | Line | Rule | Result | Detail |", "|---|---|---|---|---|", *rows]
    cases = {c["case_id"]: c for c in load_cases()}
    left = []
    for case_id in sorted(D_GOLD_1):
        claim = json.loads(json.dumps(cases[case_id]["given"]["claim"]))
        claim["diagnoses"] = [REPLACEMENT.get(d, d) for d in claim["diagnoses"]]
        left += [f"{case_id} line {h.line_no} {h.rule}" for h in proposed(claim, lookups)]
    out += [
        "",
        f"{len(rows)} hits. With {REPLACEMENT} in the D-GOLD-1 cases "
        f"({', '.join(sorted(D_GOLD_1))}), checks still failing: {left or 'none'}.",
        "",
        "## Golden end-to-end claims (30): changes",
        "",
    ]
    rows = e2e_changes(lookups)
    out += ["| Case | Line | Rule | Result | Detail |", "|---|---|---|---|---|", *rows]
    out += ["", f"{len(rows)} hits.", ""]

    records = load_records()
    out += [
        f"## Model v1 dataset ({len(records)} records): lines caught",
        "",
        "Label = the line's current label (source and decision).",
        "",
        "| Check | Result <- label | Train | Validation | Test | All |",
        "|---|---|---|---|---|---|",
    ]
    variants: list[tuple[str, Callable[[list[Line]], list[Hit]]]] = [
        ("R14", check_r14),
        ("R15 (group sets, as V1a)", lambda ls: check_r15(ls, lookups, exact=False)),
        ("R15 (approved, article-exact)", lambda ls: check_r15(ls, lookups)),
        ("R16", check_r16),
        ("R17", check_r17),
        ("R18", check_r18),
        ("R19", check_r19),
        ("R20", check_r20),
    ]
    totals = {}
    for name, check in variants:
        rows, counts = dataset_table(records, check, name)
        out += rows or [f"| {name} | none | 0 | 0 | 0 | 0 |"]
        totals[name] = counts

    r15 = totals["R15 (group sets, as V1a)"]
    decided = sum(n for (_, w), n in r15.items() if "<- RULE" not in w)
    decided_deny = sum(n for (_, w), n in r15.items() if w.endswith("<- MODEL DENY"))
    exact = totals["R15 (approved, article-exact)"]
    out += [
        "",
        "## Comparison with V1a",
        "",
        f"- R15 (group sets) on lines the rules left to the model: {decided} "
        f"(MODEL DENY {decided_deny}); V1a: 391, all DENY.",
        f"- R15 approved minus group sets: {sum(exact.values()) - sum(r15.values())} lines.",
    ]
    changed: Counter[str] = Counter()
    for r in records:
        for x in lines_of(r.claim):
            if r15_supported(x, lookups, False) != r15_supported(x, lookups, True):
                changed[f"{x.code} {r.split} {r.labels.get(x.line_no, '?')}"] += 1
    out += [
        "- Lines whose R15 result differs between the v1 group sets and the approved definition "
        "(66982 on group 1 only, colonoscopy 2A first, foot care Q7-Q9): "
        + (", ".join(f"{k} {n}" for k, n in sorted(changed.items())) or "none")
    ]
    r14 = totals["R14"]
    became = sum(n for (_, w), n in r14.items() if w.endswith(("MODEL APPROVE", "MODEL PEND")))
    already = sum(n for (_, w), n in r14.items() if w.endswith("DENY"))
    out += [
        f"- R14: {sum(r14.values())} ESI lines; would become DENY {became}, already DENY "
        f"{already}; V1a: 32 lines, 20 becoming DENY, 12 already DENY.",
    ]
    by_scenario: Counter[str] = Counter()
    for r in records:
        for h in check_r15(lines_of(r.claim), lookups, exact=False):
            if not r.labels.get(h.line_no, "").startswith("RULE"):
                by_scenario[r.scenario] += 1
    out += [
        "- R15 (group sets) by scenario, lines left to the model: "
        + ", ".join(f"{s} {n}" for s, n in by_scenario.most_common())
    ]

    claim_level = 0
    for r in records:
        lines = lines_of(r.claim)
        for x in lines:
            support = lookups.curated.diagnosis_support.get(x.code)
            if support is None or support.billing_article != "A58565":
                continue
            whole = Line(**{**x.__dict__, "diagnoses": tuple(r.claim["diagnoses"])})
            if r15_supported(x, lookups, False) is False and r15_supported(whole, lookups, False):
                claim_level += 1
    out += [
        f"- A58565 lines that fail on their own diagnoses but pass on the claim's (the article "
        f'says "the claim must have"): {claim_level}.',
    ]

    contradicting: Counter[str] = Counter()
    for r in records:
        lines = lines_of(r.claim)
        by_no = {x.line_no: x for x in lines}
        for h in check_r17(lines):
            label = r.labels.get(h.line_no, "")
            if label in ("MODEL APPROVE", "MODEL PEND") and not (
                CARPAL_TUNNEL & set(by_no[h.line_no].diagnoses)
            ):
                contradicting[f"{r.split} {label}"] += 1
    out += [
        "- R17-flagged lines without a carpal tunnel diagnosis labelled APPROVE or PEND "
        "(contradict L34594 cov-037; D-RULE-6): "
        + ", ".join(f"{k} {n}" for k, n in sorted(contradicting.items()))
        + f" (total {sum(contradicting.values())})",
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
