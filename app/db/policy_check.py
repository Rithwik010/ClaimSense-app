"""Coverage policy format checker (INSTRUCTIONS.md §11, P3.1).

Checks each file in `data/curated/coverage_policies/v1/` on its own: front matter keys and values,
criterion headings numbered c1, c2, ... under the policy's ID, and one `Source:` line per criterion
that cites the policy's own LCD and version. Cross-file consistency (procedure scope, diagnosis
support) is `validate_curated`'s job.

    uv run python -m app.db.policy_check
"""

import re
import sys
from datetime import date
from pathlib import Path

import yaml

from app.db.curated import CURATED_DIR, load_curated

REQUIRED_KEYS = {
    "policy_id",
    "title",
    "procedure_codes",
    "plan_ids",
    "effective_date",
    "sources",
    "billing_article",
    "split",
}
SPLITS = {"TRAIN", "TEST_ONLY"}
POLICY_ID = re.compile(r"^POL-[A-Z]+-[0-9]{3}$")
PROCEDURE_CODE = re.compile(r"^([0-9]{4}[0-9A-Z]|[A-Z][0-9]{4})$")
BILLING_ARTICLE = re.compile(r"^A[0-9]+$")
LCD = re.compile(r"LCD (L[0-9]+) version ([0-9]+)")
SOURCE_LCD = re.compile(r"^Source: LCD (L[0-9]+) v([0-9]+)\b")
HEADING = re.compile(r"^#+ ")
CRITERION_HEADING = re.compile(r"^## (POL-[A-Z]+-[0-9]{3})\.c([0-9]+)\s*$")


def _front_matter(text: str) -> tuple[dict | None, str, list[str]]:
    if not text.startswith("---\n"):
        return None, text, ["no front matter: the file must start with a --- line"]
    end = text.find("\n---\n", 4)
    if end < 0:
        return None, text, ["front matter is not closed with a --- line"]
    try:
        meta = yaml.safe_load(text[4:end])
    except yaml.YAMLError as exc:
        return None, text, [f"front matter is not valid YAML ({type(exc).__name__})"]
    if not isinstance(meta, dict):
        return None, text, ["front matter is not a mapping"]
    return meta, text[end + 5 :], []


def _check_meta(meta: dict, stem: str, plan_ids: set[str]) -> list[str]:
    problems = [f"missing {key}" for key in sorted(REQUIRED_KEYS - set(meta))]
    problems += [f"unknown key {key}" for key in sorted(set(meta) - REQUIRED_KEYS)]
    policy_id = meta.get("policy_id")
    if "policy_id" in meta:
        if not isinstance(policy_id, str) or not POLICY_ID.match(policy_id):
            problems.append(f"policy_id {policy_id!r} is not like POL-ABC-001")
        elif policy_id != stem:
            problems.append(f"policy_id {policy_id} does not match the file name {stem}.md")
    if "title" in meta and not (isinstance(meta["title"], str) and meta["title"].strip()):
        problems.append("title is empty")
    codes = meta.get("procedure_codes")
    if "procedure_codes" in meta:
        if not isinstance(codes, list) or not codes:
            problems.append("procedure_codes must be a non-empty list")
        else:
            problems += [
                f"procedure code {code} is not a CPT/HCPCS code"
                for code in codes
                if not PROCEDURE_CODE.match(str(code))
            ]
    plans = meta.get("plan_ids")
    if "plan_ids" in meta:
        if not isinstance(plans, list) or not plans:
            problems.append("plan_ids must be a non-empty list")
        else:
            problems += [
                f"unknown plan {plan}" for plan in plans if plan != "ALL" and plan not in plan_ids
            ]
    if "effective_date" in meta and not isinstance(meta["effective_date"], date):
        problems.append("effective_date must be a date (YYYY-MM-DD)")
    sources = meta.get("sources")
    if "sources" in meta and (
        not isinstance(sources, list) or not sources or not all(LCD.search(str(s)) for s in sources)
    ):
        problems.append("sources must list the LCD as 'LCD L<number> version <n>'")
    if "billing_article" in meta and not BILLING_ARTICLE.match(str(meta["billing_article"])):
        problems.append("billing_article must be like A12345")
    if "split" in meta and meta["split"] not in SPLITS:
        problems.append(f"split must be one of {sorted(SPLITS)}")
    return problems


def _check_body(body: str, policy_id: str, lcds: set[tuple[str, str]]) -> list[str]:
    problems: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    for line in body.splitlines():
        heading = CRITERION_HEADING.match(line)
        if heading:
            sections.append((line, []))
        elif HEADING.match(line):
            problems.append(f"unexpected heading {line.strip()!r}")
        elif sections:
            sections[-1][1].append(line.strip())
        elif line.strip():
            problems.append("text before the first criterion")
    if not sections:
        return problems + ["no criteria"]
    for number, (heading_line, lines) in enumerate(sections, start=1):
        match = CRITERION_HEADING.match(heading_line)
        assert match is not None
        owner, found = match.group(1), int(match.group(2))
        label = f"{owner}.c{found}"
        if owner != policy_id:
            problems.append(f"{label} belongs to another policy")
        if found != number:
            problems.append(f"criterion IDs must run c1, c2, ...: expected c{number}, got {label}")
        content = [line for line in lines if line]
        sources = [line for line in content if line.startswith("Source:")]
        if not [line for line in content if not line.startswith("Source:")]:
            problems.append(f"{label} has no text")
        if len(sources) != 1:
            problems.append(f"{label} needs exactly one Source line, found {len(sources)}")
            continue
        cited = SOURCE_LCD.match(sources[0])
        if not cited:
            problems.append(f"{label} Source line must start 'Source: LCD L<number> v<n>'")
        elif lcds and (cited.group(1), cited.group(2)) not in lcds:
            problems.append(
                f"{label} cites LCD {cited.group(1)} v{cited.group(2)}, which is not in sources"
            )
    return problems


def check_policy_text(name: str, text: str, plan_ids: set[str]) -> list[str]:
    meta, body, problems = _front_matter(text)
    if meta is None:
        return problems
    stem = Path(name).stem
    problems = _check_meta(meta, stem, plan_ids)
    policy_id = meta.get("policy_id") if isinstance(meta.get("policy_id"), str) else stem
    lcds = {m.groups() for s in meta.get("sources") or [] for m in LCD.finditer(str(s))}
    return problems + _check_body(body, policy_id, lcds)


def check_policy_file(path: Path) -> list[str]:
    return check_policy_text(path.name, path.read_text(encoding="utf-8"), set(load_curated().plans))


def main(argv: list[str] | None = None) -> int:
    directory = Path(argv[0]) if argv else CURATED_DIR / "coverage_policies" / "v1"
    paths = sorted(directory.glob("*.md"))
    total = 0
    for path in paths:
        for problem in check_policy_file(path):
            print(f"{path.name}: {problem}")
            total += 1
    print(f"{len(paths)} policies checked, {total} problems")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
