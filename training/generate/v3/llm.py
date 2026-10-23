"""Prompts for the open-weight models (generator v3, Phases 3 and 4; SPEC.md).

Writers B and C get the fact sheet and a style card and must state every documented fact in one
sentence of its own with its numbers and dates unchanged, contradictions and hedges as specified,
the distractors, and nothing about the missing facts; no outcome words. The verifier (a model family
no writer uses) gets the note and a numbered list of plain statements and answers, for each, the
exact sentence that states it or null. Prompts are built here and run in a private Kaggle notebook
(training/generate/v3/kaggle.py); nothing calls an outside API.
"""

import json
import random
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
HUMAN_STYLE = (  # writer D only (D-V3-15): the physician's own words
    "the physician's own words, written fast between patients: very terse, heavy use of the "
    "physician's own abbreviations and shorthand, sentence fragments rather than sentences, and "
    "sections in an order of your choosing (for example the plan first, or no headings at all); "
    "not a template, not full prose"
)
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
    "line about the task, no explanation before or after it, no markdown. Write it the way a "
    "busy clinician writes, in your own words: never copy the wording, labels or numbering of "
    "the request into the note."
)
ROUTINE_ITEMS = 8  # routine lines offered to a model writer for reaching the length
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
JUDGE_SYSTEM = (  # the second look at a missing fact the verifier found (D-V3-12)
    "You check one statement against one passage copied from a clinical note. Decide from the "
    "passage alone whether it establishes the statement. Answer with JSON only."
)
JUDGE_USER = (
    "PASSAGE:\n<passage>\n{passage}\n</passage>\n\nSTATEMENT: {statement}\n\n"
    "Does the passage itself establish the statement? It does not when it only names the "
    "procedure or test being requested or planned, when it is about a different problem, or when "
    "it covers only part of what the statement asks for. A diagnosis establishes the statement "
    "only when the statement asks for that condition itself. A listed diagnosis counts as a "
    "known condition when the statement asks for one.\n"
    'Answer with JSON only: {{"answer": "yes"}} or {{"answer": "no"}}'
)


def _date(value: str) -> str:
    return date.fromisoformat(value).strftime("%m/%d/%Y")


def _lower_first(text: str) -> str:
    """The first letter in lower case, unless the word is an acronym ("MRI of the ...")."""
    return text if text[1:2].isupper() else text[:1].lower() + text[1:]


def _dotted(code: str) -> str:
    return f"{code[:3]}.{code[3:]}" if len(code) > 3 else code


def _report_title(sheet: Mapping[str, Any], kind: str) -> str:
    clinic = phrases("sections")["clinics"].get(sheet["clinic"]["provider_type"])
    titles = (clinic or {}).get("report_titles", {}).get(kind) or ["REPORT"]
    return titles[0]


def writer_messages(sheet: Mapping[str, Any]) -> list[dict[str, str]]:
    """The chat messages for writer B, C or D (writer D: one user message, the physician's own
    words, the facts in an order of its choosing; D-V3-15)."""
    cfg = config()
    style = sheet["style"]
    human = sheet["writer"] == "D"
    patient = sheet["patient"]
    lines = [
        "Write the clinic note for this visit.",
        "",
        f"Clinic: {sheet['clinic']['name']}. Visit: {sheet['clinic']['visit'].lower()} on "
        f"{_date(sheet['visit_date'])}.",
        f"Patient: {patient['age']}-year-old {patient['sex_words'][0]}.",
    ]
    if human:
        lines.append(f"Author style: {HUMAN_STYLE}.")
    elif sheet["writer"] == "C" and style.get("format"):
        lines.append(f"Format: {FORMATS[style['format']]}.")
    else:
        lines.append(f"Author style: {HABITS[style['habit']]}.")
    words = cfg["llm"]["writer_d"]["target_words"] if human else cfg["note"]["length_words"]
    target = min(style["target_words"], words["max"])
    if human:
        target = max(words["min"], target)
    low, high = max(words["min"], round(target * 0.85)), min(words["max"], round(target * 1.15))
    lines.append(
        f"Length: between {low} and {high} words (about {target}). A note under {low} words "
        "cannot be used."
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
        "and date exactly as written (you may reword everything else):"
        if not human
        else "The note must state each of these facts in a fragment or line of its own, keeping "
        "every number and date exactly as written (abbreviate and reword everything else):",
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
                f'"Copied from a prior note:", state: {original} Then correct it in the '
                "Assessment section (a later section, never the same paragraph as the copied "
                f'text) with a sentence that starts "{fact["marker"]}" and states: {sentence}'
            )
            continue
        if report and fact["fact_id"] in timeline:
            event = timeline[fact["fact_id"]]
            where = "Results, as " + REPORTS[report].format(
                title=_report_title(sheet, report), date=_date(event["date"]), event=event["event"]
            )
        lines.append(f"{n}. {sentence}" if human else f"{n}. [{where}] {sentence}")
    if hedges:
        lines += ["", "Mention each of these only as a hedged, unconfirmed possibility:"]
        lines += [f"- {h}" for h in hedges]
    if negatives:
        lines += ["", "State each of these negatives:"]
        lines += [f"- {x}" for x in negatives]
    dis = sheet["distractors"]
    lines += ["", "Background to work into the note, unrelated to the reason for the visit:"]
    if dis["conditions"]:
        lines.append("- conditions: " + "; ".join(c["text"][0] for c in dis["conditions"]))
    if dis.get("past"):
        past = dis["past"]["text"][0].format(year=dis["past"]["year"])
        lines.append(f"- a resolved problem from the past: {past}")
    if dis["medications"]:
        lines.append("- current medicines: " + "; ".join(m[0] for m in dis["medications"]))
    lines.append("- allergies: " + dis["allergies"][0])
    lines.append("- social: " + " ".join(s[0] for s in dis["social"]))
    if dis["ros"]:
        lines.append(
            "- review of systems, negatives only, some of: " + " ".join(r[0] for r in dis["ros"])
        )
    lines.append(
        "- in the Assessment, these diagnoses with their codes: "
        + "; ".join(f"{d['description']} ({_dotted(d['code'])})" for d in sheet["diagnoses"])
    )
    if sheet.get("procedures"):
        lines.append("- in the Plan: " + "; ".join(_lower_first(p) for p in sheet["procedures"]))
    if style.get("copy_forward"):
        lines.append(
            "- in the history, a short block copied forward from an earlier visit, marked as "
            "copied, with no new clinical facts"
        )
    routine = [] if human else _routine(sheet)
    if routine:
        lines += [
            "",
            "To reach the length, you may also use routine lines like these (reworded), and "
            "nothing else that is new:",
        ]
        lines += [f"- {r}" for r in routine]
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
        "Use only sections that have something in them; never write a section that only says "
        'there is nothing to report (such as "No relevant admissions").',
        "Do not copy the wording of this request into the note: no headings such as "
        '"Background", "conditions:" or "a resolved problem from the past", and no bracketed '
        "section names or item numbers.",
        f'Never use these words: {BANNED}. Write negatives as "no", "reports no" or '
        '"negative for".',
    ]
    if human:  # Mistral's chat template takes no system message
        return [{"role": "user", "content": WRITER_SYSTEM + "\n\n" + "\n".join(lines)}]
    return [
        {"role": "system", "content": WRITER_SYSTEM},
        {"role": "user", "content": "\n".join(lines)},
    ]


def _routine(sheet: Mapping[str, Any]) -> list[str]:
    """Routine lines writer A may also use (its filler and long-note pools, without the topics
    the clinic excludes), a few per sheet: what a model writer may add to reach the length."""
    sec = phrases("sections")
    clinic = sec["clinics"].get(sheet["clinic"]["provider_type"]) or {}
    exclude = set(clinic.get("exclude", ()))
    pool = [
        item["text"][0]
        for key in ("filler", "exam_systems", "education", "coordination")
        for item in sec[key]
        if not set(item["topics"]) & exclude and "{" not in item["text"][0]
    ]
    rng = random.Random(f"{sheet['seed']}-routine")
    return rng.sample(pool, min(ROUTINE_ITEMS, len(pool)))


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
                    "check": "judge",  # a finding gets the judge's second look
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
                    "check": "look",  # a finding gets the second look: asked again, alone
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


NO_QUOTE = {"", "null", "none", "n/a", "na", "not stated", "not found", "no"}
OUTCOME_WORDS = (  # model notes only: clinical wordings of banned words, made neutral (D-V3-10)
    (re.compile(r"\bdenies any\b"), "reports no"),
    (re.compile(r"\bDenies any\b"), "Reports no"),
    (re.compile(r"\bdenies\b"), "reports no"),
    (re.compile(r"\bDenies\b"), "Reports no"),
    (re.compile(r"\bdenying\b"), "reporting no"),
    (re.compile(r"\bpending\b"), "awaited"),
    (re.compile(r"\bPending\b"), "Awaited"),
)


def neutral_words(text: str) -> tuple[str, int]:
    """A model note with "denies" written as "reports no" and "pending" as "awaited", and how many
    were changed: the models use them though told not to, and the leakage check refuses them."""
    changed = 0
    for pattern, replacement in OUTCOME_WORDS:
        text, n = pattern.subn(replacement, text)
        changed += n
    return text, changed


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
            empty = not isinstance(quote, str) or quote.strip().strip(".'\"").lower() in NO_QUOTE
            found[answer["id"]] = None if empty else quote
    return found


def judge_messages(passage: str, statement: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": JUDGE_USER.format(passage=passage, statement=statement)},
    ]


def parse_judge(text: str) -> bool:
    """The judge's yes (True) or no (False); ValueError when it answered neither."""
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            answer = json.loads(text[start : end + 1]).get("answer")
        except (ValueError, AttributeError):
            answer = None
        if isinstance(answer, str) and answer.strip().lower() in ("yes", "no"):
            return answer.strip().lower() == "yes"
    raise ValueError(f"no yes or no answer: {text[:80]!r}")


def clean_note(text: str) -> str:
    """A model's note without wrappers it may add (code fences, a "Here is the note" line)."""
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n|\n```$", "", text).strip()
    first, _, rest = text.partition("\n")
    if re.match(r"^(here is|here's|below is|sure)\b", first.strip(), re.IGNORECASE) and rest:
        text = rest.strip()
    return text
