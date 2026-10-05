"""Rule tables for tests and CI from the committed fixture of the rows the golden cases need
(tests/golden/rules/raw_subset.json, D-CI-1), in the shape app.db.seed.load_rule_tables loads.

The fixture holds codes, dates, indicators and limits only, so place-of-service names, ICD-10-CM
descriptions and MUE adjudication indicators are empty here."""

from datetime import date

from app.db import raw
from app.db.seed import ROOT, RuleTableData, Source, file_sha256
from scripts.verify.rules_fixture import FIXTURE, read_fixture


def fixture_rule_tables() -> RuleTableData:
    data = read_fixture()
    source = (Source(FIXTURE.relative_to(ROOT).as_posix(), file_sha256(FIXTURE)),)

    def ncci_rows() -> list[raw.NcciEditRow]:
        return [
            (
                column1,
                column2,
                date.fromisoformat(effective),
                date.fromisoformat(deletion) if deletion else None,
                indicator,
            )
            for column1, column2, effective, deletion, indicator in data["ncci"]
        ]

    return RuleTableData(
        place_of_service=dict.fromkeys(data["place_of_service_codes"], ""),
        procedure_codes=data["procedure_codes"],
        icd10={int(year): dict.fromkeys(codes, "") for year, codes in data["icd10_codes"].items()},
        mue={code: (units, "") for code, units in data["mue"].items()},
        mue_effective=raw.MUE_EFFECTIVE,
        ncci_rows=lambda: iter(ncci_rows()),
        sources={
            table: source
            for table in (
                "place_of_service_codes",
                "procedure_codes",
                "icd10_codes",
                "mue_limits",
                "ncci_ptp_edits",
            )
        },
    )
