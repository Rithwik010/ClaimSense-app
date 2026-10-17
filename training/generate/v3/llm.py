"""Prompts for the open-weight models (generator v3, Phases 3 and 4; SPEC.md).

Writers B and C get the fact sheet and a style card and must state every documented fact in one
sentence of its own with its numbers and dates unchanged, contradictions and hedges as specified,
the distractors, and nothing about the missing facts; no outcome words. The verifier (a model family
no writer uses) gets the note and a numbered list of plain statements and answers, for each, the
exact sentence that states it or null. Prompts are built here and run in a private Kaggle notebook
(training/generate/v3/kaggle.py); nothing calls an outside API.
"""

import json
import re
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from training.generate.v3.config import config, phrases

SECTION_NAMES = {
    "chief_complaint": "Chief complaint",
    "hpi": "History of present illness",
    "past_history": "Past medical history",
    "medications": "Medications",
    "allergies": "Allergies",
    "social_history": "Social history",
    "review_of_systems": "Review of systems",
    "exam": "Exam",
    "results": "Results",
    "assessment": "Assessment",
    "plan": "Plan",
}
HABITS = {
    "terse_abbreviated": "terse, heavily abbreviated clinical shorthand (pt, c/o, hx, s/p, w/, "
    "x6wks, f/u), mostly fragments rather than full sentences",
    "full_sentences": "complete sentences in plain clinical English",
    "dictated": "dictated style: long run-on sentences, as transcribed from voice, with few "
    "headers",
    "templated_ehr": "an EHR template with upper-case section headers, short labeled fields and "
    "lists",
}
FORMATS = {  # writer C only
    "soap": "SOAP format with S, O, A and P sections",
    "problem_oriented": "a problem-oriented note: a brief history and exam, then a numbered "
    "problem list, each problem with its own assessment and plan",
    "narrative_letter": "a consultation letter to the referring physician, in paragraphs",
}
REPORTS = {
    "imaging_report": 'an embedded imaging report titled "{title}" dated {date}, with FINDINGS '
    "and IMPRESSION lines; the fact is the impression",
    "therapy_summary": 'an embedded summary titled "{title}" dated {date}; the fact is its content',
    "prior_procedure": 'an embedded prior-procedure entry: "{title}: {event} on {date}", then '
    '"RESPONSE:" followed by the fact',
}
BANNED = (
    "approve, approved, approval, deny, denies, denied, denial, pend, pended, pending, reject, "
    "rejected, covered, coverage, medically necessary, medical necessity"
)
WRITER_SYSTEM = (
    "You are a clinician writing an outpatient clinic note in plain text for a synthetic training "
    "dataset. Everything about the patient is fictional. Write only the note itself: no title "
    "line about the task, no explanation before or after it, no markdown."
)
VERIFIER_SYSTEM = (
    "You compare a clinical note with a numbered list of statements. For each statement, decide "
    "whether the note states that fact, even if the wording differs. If it does, copy the single "
    "sentence of the note that states it, character for character. If the note does not state "
    "it, answer null. A hedged or uncertain mention, or a statement that something is absent, "
    "does not state the fact. Answer with JSON only."
)
VERIFIER_USER = (
    "NOTE:\n<note>\n{note}\n</note>\n\nSTATEMENTS:\n{statements}\n\n"
    'Answer with JSON only, in this form: {{"answers": [{{"id": 1, "quote": "..."}}, '
    '{{"id": 2, "quote": null}}]}}'
)


def _date(value: str) -> str:
    return date.fromisoformat(value).strftime("%m/%d/%Y")


def _dotted(code: str) -> str:
    return f"{code[:3]}.{code[3:]}" if len(code) > 3 else code


def _report_title(sheet: Mapping[str, Any], kind: str) -> str:
    clinic = phrases("sections")["clinics"].get(sheet["clinic"]["provider_type"])
    titles = (clinic or {}).get("report_titles", {}).get(kind) or ["REPORT"]
    return titles[0]


def writer_messages(sheet: Mapping[str, Any]) -> list[dict[str, str]]:
    """The chat messages for writer B or C."""
    cfg = config()
    style = sheet["style"]
    patient = sheet["patient"]
    lines = [
        "Write the clinic note for this visit.",
        "",
        f"Clinic: {sheet['clinic']['name']}. Visit: {sheet['clinic']['visit'].lower()} on "
        f"{_date(sheet['visit_date'])}.",
        f"Patient: {patient['age']}-year-old {patient['sex_words'][0]}.",
    ]
    if sheet["writer"] == "C" and style.get("format"):
        lines.append(f"Format: {FORMATS[style['format']]}.")
    else:
        lines.append(f"Author style: {HABITS[style['habit']]}.")
    lines.append(
        f"Length: about {style['target_words']} words; never more than "
        f"{cfg['note']['length_words']['max']} words."
    )
    if sheet.get("lead"):
        lines.append(
            f"Reason for the visit: {sheet['lead'].get('A') or next(iter(sheet['lead'].values()))}"
        )
    earlier = [v for v in sheet.get("office_visits", []) if v["date"] != sheet["visit_date"]]
    if earlier:
        dates = ", ".join(_date(v["date"]) for v in earlier)
        lines.append(f"Earlier office visits in this clinic: {dates}.")
    lines += [
        "",
        "The note must state each of these facts in a sentence of its own, keeping every number "
        "and date exactly as written (you may reword everything else):",
    ]
    timeline = {e.get("fact_id"): e for e in sheet["timeline"]}
    n = 0
    hedges, negatives = [], []
    for fact in sheet["facts"]:
        if fact.get("hedge"):
            hedges.append(fact["hedge"].get("A") or next(iter(fact["hedge"].values())))
        if fact.get("negated"):
            negatives.append(fact["negated"].get("A") or next(iter(fact["negated"].values())))
        text = fact.get("text") or {}
        if not text or fact["status"] in ("missing", "absent"):
            continue
        n += 1
        sentence = text.get("A") or next(iter(text.values()))
        placement = fact.get("placement") or {}
        where = SECTION_NAMES.get(placement.get("section", "hpi"), "History of present illness")
        report = placement.get("report")
        if fact["status"] == "contradicted":
            original = fact["original"].get("A") or next(iter(fact["original"].values()))
            lines.append(
                f"{n}. [History] As text copied forward from an earlier visit, introduced with "
                f'"Copied from a prior note:", state: {original} Later, in the Assessment, '
                f'correct it with a sentence that starts "{fact["marker"]}" and states: {sentence}'
            )
            continue
        if report and fact["fact_id"] in timeline:
            event = timeline[fact["fact_id"]]
            where = "Results, as " + REPORTS[report].format(
                title=_report_title(sheet, report), date=_date(event["date"]), event=event["event"]
            )
        lines.append(f"{n}. [{where}] {sentence}")
    if hedges:
        lines += ["", "Mention each of these only as a hedged, unconfirmed possibility:"]
        lines += [f"- {h}" for h in hedges]
    if negatives:
        lines += ["", "State each of these negatives:"]
        lines += [f"- {x}" for x in negatives]
    dis = sheet["distractors"]
    lines += ["", "Also include (unrelated to the reason for the visit):"]
    if dis["conditions"]:
        lines.append(
            "- Past medical history: " + "; ".join(c["text"][0] for c in dis["conditions"])
        )
    if dis.get("past"):
        lines.append(
            "- A past episode, over now: " + dis["past"]["text"][0].format(year=dis["past"]["year"])
        )
    if dis["medications"]:
        lines.append("- Medications: " + "; ".join(m[0] for m in dis["medications"]))
    lines.append("- Allergies: " + dis["allergies"][0])
    lines.append("- Social history: " + " ".join(s[0] for s in dis["social"]))
    if dis["ros"]:
        lines.append(
            "- Review of systems, negatives only, chosen from: "
            + " ".join(r[0] for r in dis["ros"])
        )
    lines.append(
        "- Assessment, listing these diagnoses with their codes: "
        + "; ".join(f"{d['description']} ({_dotted(d['code'])})" for d in sheet["diagnoses"])
    )
    if sheet.get("procedures"):
        lines.append("- Plan: " + "; ".join(p[0].lower() + p[1:] for p in sheet["procedures"]))
    if style.get("copy_forward"):
        lines.append(
            "- Somewhere in the history, a short block copied forward from an earlier visit, "
            "marked as copied, with no new clinical facts."
        )
    absent = _absent_topics(sheet)
    if absent:
        lines += [
            "",
            "Leave these topics out completely: do not mention, hint at or invent anything about:",
        ]
        lines += [f"- {a}" for a in absent]
    lines += [
        "",
        "Do not add any symptom, finding, test result, treatment, procedure or history that is not "
        "listed above.",
        f'Never use these words: {BANNED}. Write negatives as "no", "reports no" or '
        '"negative for".',
    ]
    return [
        {"role": "system", "content": WRITER_SYSTEM},
        {"role": "user", "content": "\n".join(lines)},
    ]


def _absent_topics(sheet: Mapping[str, Any]) -> list[str]:
    topics = []
    for fact in sheet["facts"]:
        if fact["status"] == "missing" and fact.get("missing_text"):
            topics.append(fact["missing_text"])
        if fact["status"] == "absent" and fact.get("role") == "exclusion" and fact.get("forbidden"):
            if not fact.get("negated"):
                topics.append("Anything like: " + _strip_slots(fact["forbidden"][0]))
    return list(dict.fromkeys(topics))


def _strip_slots(text: str) -> str:
    return re.sub(r"\s*\{[^}]+\}", "", text)


# --- verifier ------------------------------------------------------------------------------------


def statements(sheet: Mapping[str, Any]) -> list[dict[str, Any]]:
    """What the verifier is asked about, in order: `expect` present (a documented fact, a copied
    statement) or absent (a missing fact, an exclusion that does not apply)."""
    found = []
    for fact in sheet["facts"]:
        text = fact.get("text") or {}
        if text and fact["status"] not in ("missing", "absent"):
            if fact["status"] == "contradicted":
                found.append(
                    {
                        "fact_id": f"{fact['fact_id']}:original",
                        "statement": fact["original"].get("A")
                        or next(iter(fact["original"].values())),
                        "expect": "present",
                    }
                )
            found.append(
                {
                    "fact_id": fact["fact_id"],
                    "statement": text.get("A") or next(iter(text.values())),
                    "expect": "present",
                    "values": fact.get("values") or [],
                }
            )
        elif fact["status"] == "missing" and fact.get("missing_text"):
            found.append(
                {
                    "fact_id": fact["fact_id"],
                    "statement": "The note documents: "
                    + fact["missing_text"][0].lower()
                    + fact["missing_text"][1:]
                    + ".",
                    "expect": "absent",
                }
            )
        elif (
            fact["status"] == "absent" and fact.get("role") == "exclusion" and fact.get("forbidden")
        ):
            found.append(
                {
                    "fact_id": fact["fact_id"],
                    "statement": _strip_slots(fact["forbidden"][0]),
                    "expect": "absent",
                }
            )
    for i, item in enumerate(found, start=1):
        item["id"] = i
    return found


def verifier_messages(note: str, items: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    listed = "\n".join(f"{item['id']}. {item['statement']}" for item in items)
    return [
        {"role": "system", "content": VERIFIER_SYSTEM},
        {"role": "user", "content": VERIFIER_USER.format(note=note, statements=listed)},
    ]


def parse_verifier(text: str) -> dict[int, str | None]:
    """{statement id: quote or None} from the verifier's answer (the first JSON object in it)."""
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object")
    data = json.loads(text[start : end + 1])
    answers = data.get("answers") if isinstance(data, dict) else None
    if not isinstance(answers, list):
        raise ValueError("no answers list")
    found: dict[int, str | None] = {}
    for answer in answers:
        if isinstance(answer, dict) and isinstance(answer.get("id"), int):
            quote = answer.get("quote")
            found[answer["id"]] = quote if isinstance(quote, str) and quote.strip() else None
    return found


def clean_note(text: str) -> str:
    """A model's note without wrappers it may add (code fences, a "Here is the note" line)."""
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n|\n```$", "", text).strip()
    first, _, rest = text.partition("\n")
    if re.match(r"^(here is|here's|below is|sure)\b", first.strip(), re.IGNORECASE) and rest:
        text = rest.strip()
    return text
