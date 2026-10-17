"""Writer A (generator v3, Phase 3): template notes from a fact sheet (SPEC.md).

A note has the sections of `note.sections` in order; a section with a fact always appears, any other
with its `note.section_presence`. Each fact's sentence is written once, protected, in its placement:
the section it names, or an embedded report block (imaging report, therapy summary, prior
procedure) with the configured chance. The rest is drawn from phrases/sections.yaml for the clinic:
the opener for the author habit, history, medications, allergies, social history, negative review
of systems, vitals and exam, results, the assessment (the claim's diagnoses with their codes) and
the plan. A contradiction's copied statement goes in a block copied from an earlier visit in the
history; its correction, with its marker, goes in the assessment, which always comes later.
Length: optional items are added until the style card's target is reached, never past
`note.length_words.max`.
"""

import random
from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from typing import Any

from training.generate.notes import draw_slots
from training.generate.v3.config import config, phrases
from training.generate.v3.segments import Segment, word_count

LIST_SECTIONS = {"past_history", "medications", "allergies", "review_of_systems", "assessment"}
REPORT_DATE = "%m/%d/%Y"


def _pick(rng: random.Random, value: Sequence[str] | str) -> str:
    return value if isinstance(value, str) else rng.choice(list(value))


def _by_wording(texts: Mapping[str, str], wording: str) -> str:
    return texts.get(wording) or texts.get("A") or next(iter(texts.values()))


def _item(texts: Sequence[str], wording: str) -> str:
    """A two-wording phrase list [plain, shorthand]."""
    return texts[1] if wording == "B" and len(texts) > 1 else texts[0]


def _dotted(code: str) -> str:
    return f"{code[:3]}.{code[3:]}" if len(code) > 3 else code


class WriterA:
    def __init__(self, sheet: Mapping[str, Any], rng: random.Random) -> None:
        self.sheet = sheet
        self.rng = rng
        self.cfg = config()
        self.sec = phrases("sections")
        self.style = sheet["style"]
        self.wording = self.style["wording"]
        self.habit = self.style["habit"]
        clinic = sheet["clinic"]["provider_type"]
        self.clinic = self.sec["clinics"].get(clinic) or self.sec["clinics"]["PRIMARY_CARE"]
        self.visit = date.fromisoformat(sheet["visit_date"])
        self.items: dict[str, list[Segment]] = {s: [] for s in self.cfg["note"]["sections"]}
        self.optional: list[tuple[str, Segment]] = []
        self.forced: set[str] = set()

    # --- pieces ----------------------------------------------------------------------------------

    def _text(self, section: str, text: str) -> Segment:
        return Segment(text=text, section=section)

    def _fact(self, section: str, fact_id: str, text: str) -> Segment:
        return Segment(text=text, section=section, fact_id=fact_id, protected=True)

    def _add(self, section: str, segment: Segment, forced: bool = False) -> None:
        self.items[section].append(segment)
        if forced:
            self.forced.add(section)

    def _date(self, days_before: int) -> str:
        return (self.visit - timedelta(days=days_before)).strftime(REPORT_DATE)

    # --- facts -----------------------------------------------------------------------------------

    def _report(self, kind: str, fact: Mapping[str, Any], sentence: str) -> list[Segment]:
        titles = self.clinic["report_titles"].get(kind) or ["REPORT"]
        title = _pick(self.rng, titles)
        event = next(
            (e for e in self.sheet["timeline"] if e.get("fact_id") == fact["fact_id"]), None
        )
        when = (
            date.fromisoformat(event["date"]).strftime(REPORT_DATE)
            if event
            else self._date(self.rng.randint(5, 60))
        )
        found = _pick(self.rng, self.clinic["report_findings"])
        if kind == "imaging_report":
            pieces = [
                Segment(f"{title} ({when})", "results", "line"),
                Segment("FINDINGS: ", "results", "marker"),
                Segment(found, "results"),
                Segment("IMPRESSION: ", "results", "marker"),
            ]
        elif kind == "prior_procedure":
            name = event["event"] if event else "procedure"
            pieces = [
                Segment(f"{title}: {name} on {when}.", "results", "line"),
                Segment("RESPONSE: ", "results", "marker"),
            ]
        else:
            pieces = [Segment(f"{title} ({when}): ", "results", "marker")]
        return [*pieces, self._fact("results", fact["fact_id"], sentence)]

    def place_facts(self) -> None:
        embedded = self.cfg["note"]["embedded_reports"]
        for fact in self.sheet["facts"]:
            fid = fact["fact_id"]
            texts = fact.get("text") or {}
            placement = fact.get("placement") or {"section": "hpi"}
            section = placement.get("section", "hpi")
            if section not in self.items:
                section = "hpi"
            if fact.get("hedge"):
                self._add(
                    section,
                    self._fact(section, f"{fid}:hedge", _by_wording(fact["hedge"], self.wording)),
                    True,
                )
            if fact.get("negated"):
                self._add(
                    section,
                    self._fact(
                        section, f"{fid}:negated", _by_wording(fact["negated"], self.wording)
                    ),
                    True,
                )
            if not texts or fact["status"] in ("missing", "absent"):
                continue
            sentence = _by_wording(texts, self.wording)
            if fact["status"] == "contradicted":
                original = _by_wording(fact["original"], self.wording)
                when = self._date(self.rng.randint(14, 60))
                marker = _pick(self.rng, self.sec["copy_forward"]["marker"]).format(date=when)
                self._add("hpi", Segment(marker, "hpi", "line"), True)
                self._add("hpi", self._fact("hpi", f"{fid}:original", original), True)
                self._add("hpi", Segment("--- end of copied text ---", "hpi", "line"), True)
                self._add("assessment", Segment(f"{fact['marker']} ", "assessment", "marker"), True)
                self._add("assessment", self._fact("assessment", fid, sentence), True)
                continue
            report = placement.get("report")
            if report and self.rng.random() < embedded.get(report, 0):
                for piece in self._report(report, fact, sentence):
                    self._add("results", piece, True)
                continue
            self._add(section, self._fact(section, fid, sentence), True)

    # --- everything else -------------------------------------------------------------------------

    def place_context(self) -> None:
        rng, w, sex = self.rng, self.wording, self.sheet["patient"]["sex_words"]
        lead = _by_wording(self.sheet["lead"], w) if self.sheet.get("lead") else None
        visit = self.sheet["clinic"]["visit"].lower()
        reason = ("an " if visit[0] in "aeiou" else "a ") + visit
        opener = _pick(rng, self.sec["openers"][self.habit]).format(
            visit=visit,
            age=self.sheet["patient"]["age"],
            sex_word=sex[0],
            sex_short=sex[2],
            Pronoun=sex[3],
            pronoun=sex[4],
            reason=reason,
        )
        if lead:
            self._add("chief_complaint", self._text("chief_complaint", lead))
        self.items["hpi"].insert(0, self._text("hpi", opener))
        for visit in self.sheet.get("office_visits", []):
            when = date.fromisoformat(visit["date"]).strftime(REPORT_DATE)
            if visit["date"] != self.sheet["visit_date"]:
                text = (
                    f"Seen in this clinic on {when} for an office visit."
                    if w == "A"
                    else f"OV {when}."
                )
                self._add("hpi", self._text("hpi", text))
        dis = self.sheet["distractors"]
        for condition in dis["conditions"]:
            self._add("past_history", self._text("past_history", _item(condition["text"], w)))
        if dis.get("past"):
            past = dis["past"]
            self._add(
                "past_history",
                self._text("past_history", _item(past["text"], w).format(year=past["year"])),
            )
        for med in dis["medications"]:
            self._add("medications", self._text("medications", _item(med, w)))
        self._add("allergies", self._text("allergies", _item(dis["allergies"], w)))
        social = dis["social"]
        self._add("social_history", self._text("social_history", _item(social[0], w)))
        self.optional.append(("social_history", self._text("social_history", _item(social[1], w))))
        ros = list(dis["ros"])
        rng.shuffle(ros)
        for i, line in enumerate(ros):
            segment = self._text("review_of_systems", _item(line, w))
            if i < 2:
                self._add("review_of_systems", segment)
            else:
                self.optional.append(("review_of_systems", segment))
        slots = draw_slots(rng, self.sec["vitals_slots"])
        self.items["exam"].insert(0, self._text("exam", self.sec["vitals"][w].format(**slots)))
        self.items["exam"].insert(1, self._text("exam", _pick(rng, self.sec["general_exam"][w])))
        for line in self.clinic["exam"]:
            self.optional.append(("exam", self._text("exam", line)))
        self.optional.append(
            ("results", self._text("results", _pick(rng, self.sec["general_results"][w])))
        )
        for dx in self.sheet["diagnoses"]:
            words = dx["description"] or "Diagnosis"
            self._add("assessment", self._text("assessment", f"{words} ({_dotted(dx['code'])})"))
        procedures = self.sheet.get("procedures") or []
        if procedures:
            listed = "; ".join(p[0].lower() + p[1:] for p in procedures)
            line = f"Procedure planned: {listed}." if w == "A" else f"Proc: {listed}."
            self.items["plan"].insert(0, self._text("plan", line))
        plan_pool = list(self.sec["plan_general"][w])
        rng.shuffle(plan_pool)
        self._add("plan", self._text("plan", plan_pool[0]))
        for line in plan_pool[1:]:
            self.optional.append(("plan", self._text("plan", line)))
        exclude = set(self.clinic.get("exclude", ()))
        for item in self.sec["filler"]:
            if not set(item["topics"]) & exclude:
                self.optional.append(
                    (item["section"], self._text(item["section"], _item(item["text"], w)))
                )
        self.longer: list[tuple[str, Segment]] = []  # after the optional items, for long notes
        for section, key in (
            ("exam", "exam_systems"),
            ("results", "labs"),
            ("plan", "education"),
            ("plan", "coordination"),
        ):
            for item in self.sec[key]:
                if set(item["topics"]) & exclude:
                    continue
                values = draw_slots(rng, item.get("slots") or {})
                values["date"] = self._date(rng.randint(10, 120))
                wording = "A" if w == "B" and rng.random() < 0.3 else w  # mixed shorthand
                text = _item(item["text"], wording).format(**values)
                self.longer.append((section, self._text(section, text)))
        if self.style.get("copy_forward"):
            cf = self.sec["copy_forward"]
            for _ in range(rng.choice((1, 1, 2))):
                when = self._date(rng.randint(14, 120))
                marker = _pick(rng, cf["marker"]).format(date=when)
                block = " ".join(rng.sample(list(cf[w]), 2))
                vitals = self.sec["copy_forward_vitals"][w].format(
                    **draw_slots(rng, self.sec["vitals_slots"])
                )
                text = f"{marker} {block} {vitals}"
                self.optional.insert(0, ("hpi", Segment(text, "hpi", "line")))

    # --- layout ----------------------------------------------------------------------------------

    def _header(self, section: str) -> str:
        names = self.sec["headers"][section]
        if self.habit == "templated_ehr":
            return _pick(self.rng, names).upper() + ":"
        if self.habit == "terse_abbreviated":
            return min(names, key=len) + ":"
        return _pick(self.rng, names) + ":"

    def assemble(self) -> list[Segment]:
        rng, cfg = self.rng, self.cfg
        presence = cfg["note"]["section_presence"]
        present = [
            s
            for s in cfg["note"]["sections"]
            if self.items[s] and (s in self.forced or s == "hpi" or rng.random() < presence[s])
        ]
        target = min(self.style["target_words"], cfg["note"]["length_words"]["max"])
        optional = list(self.optional)
        rng.shuffle(optional)
        longer = list(getattr(self, "longer", []))
        rng.shuffle(longer)
        optional += longer
        while optional and self._words(present) < target:
            section, segment = optional.pop(0)
            self.items[section].append(segment)
            if section not in present:
                present.append(section)
                present.sort(key=cfg["note"]["sections"].index)
        out: list[Segment] = []
        for section in present:
            out += self._section(section)
        return out

    def _words(self, present: Sequence[str]) -> int:
        return sum(word_count(self.items[s]) for s in present)

    def _section(self, section: str) -> list[Segment]:
        items = self.items[section]
        dictated = self.habit == "dictated" and section in ("hpi", "chief_complaint")
        out = []
        if not dictated:
            out.append(Segment(text=self._header(section), section=section, role="header"))
        listed = section in LIST_SECTIONS
        out.append(
            Segment(text="\n" if (listed or not dictated) else "", section=section, role="sep")
        )
        for i, item in enumerate(items):
            if i:
                if items[i - 1].role == "marker":
                    sep = ""
                elif listed or item.role in ("line", "marker") or items[i - 1].role == "line":
                    sep = "\n"
                else:
                    sep = " "
                out.append(Segment(text=sep, section=section, role="sep"))
            text = item
            if section == "assessment" and item.role == "text" and not item.protected:
                bullet = f"{i + 1}." if self.habit in ("full_sentences", "dictated") else "-"
                text = item.with_text(f"{bullet} {item.text}")
            out.append(text)
        out.append(Segment(text="\n\n", section=section, role="sep"))
        return out


def write(sheet: Mapping[str, Any], seed: str) -> list[Segment]:
    """Writer A's note for a sheet, as segments (render with segments.render)."""
    writer = WriterA(sheet, random.Random(seed))
    writer.place_facts()
    writer.place_context()
    return writer.assemble()
