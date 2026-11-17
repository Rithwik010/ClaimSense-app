// The member's plan assistant, as a preview (D-MEM-4): a button on every member page opens a panel
// with quick questions answered from the member's own records, as the member pages already read
// them (GET /v1/member/benefits and /v1/member/claims). A question typed in one's own words is
// matched to one of these by its words (matchQuestion, in the browser); one it cannot match gets
// the list of what it can answer. No model is called: each answer is the API's values in a fixed
// sentence, formatted only; nothing is computed (what is left of a limit is the calculator's,
// D-MEM-5).

import { MessageCircleQuestion, Send } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import { useMemberBenefits, useMemberClaims } from "@/api/hooks";
import type { MemberBenefits, MemberClaim } from "@/api/types";
import { PlainBadge } from "@/components/Chip";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { dateOnly, money } from "@/lib/format";
import { benefitCategory, memberOutcome } from "@/lib/labels";

type Question = "deductible" | "latest" | "visits" | "oop" | "plan" | "appeal" | "unknown";

const QUESTIONS: { id: Question; text: string }[] = [
  { id: "deductible", text: "How much of my deductible have I met?" },
  { id: "latest", text: "What is the status of my latest claim?" },
  { id: "visits", text: "How many visits have I used this year?" },
  { id: "oop", text: "How close am I to my out-of-pocket maximum?" },
  { id: "plan", text: "What does my plan cover?" },
  { id: "appeal", text: "Can I appeal a denied claim?" },
];

/** Words that point at each question; the first question with a match wins (in this order). */
const MATCHES: [Question, RegExp][] = [
  ["appeal", /\b(appeal|disagree|unfair|wrong decision|decide again|reconsider)/i],
  ["oop", /(out[\s-]*of[\s-]*pocket|\boop\b|maximum|max\b|most i (?:will |would )?pay)/i],
  ["deductible", /deductib/i],
  ["visits", /\b(visits?|therapy|physio|sessions?)\b/i],
  ["latest", /\b(claims?|status|latest|last|recent|processed|paid|bill)\b/i],
  ["plan", /\b(cover(?:ed|s|age)?|copays?|coinsurance|benefits?|plan|referral|prior auth|summary)\b/i],
];

/** The question a typed one is about, by its words; "unknown" when none matches. */
export function matchQuestion(text: string): Question {
  return MATCHES.find(([, words]) => words.test(text))?.[0] ?? "unknown";
}

const NETWORKS: Record<string, string> = { IN_NETWORK: "In network", OUT_OF_NETWORK: "Out of network" };

function Deductible({ benefits }: { benefits: MemberBenefits }) {
  return (
    <>
      <p>
        For {benefits.plan_name}, benefit year {dateOnly(benefits.benefit_year_start)} to{" "}
        {dateOnly(benefits.benefit_year_end)}, as recorded on {dateOnly(benefits.as_of)}:
      </p>
      <ul className="my-2 list-disc pl-5">
        {benefits.networks.map((n) => (
          <li key={n.network}>
            {NETWORKS[n.network] ?? n.network}: you have met {money(n.deductible_met_cents)} of your{" "}
            {money(n.deductible_cents)} deductible.
          </li>
        ))}
      </ul>
      <p>A claim still being processed is not counted yet.</p>
      <Link to="/member/benefits" className="mt-2 inline-block font-semibold text-link underline">
        See My benefits
      </Link>
    </>
  );
}

function Latest({ claims }: { claims: MemberClaim[] }) {
  // The most recently received claim (ISO dates sort as text); the claim ID breaks a tie.
  const latest = [...claims].sort((a, b) => b.received.localeCompare(a.received) || b.claim_id.localeCompare(a.claim_id))[0];
  if (!latest) return <p>You have no claims on file yet.</p>;
  const care = [
    latest.service_date ? `for care on ${dateOnly(latest.service_date)}` : null,
    latest.provider_name ? `with ${latest.provider_name}` : null,
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <>
      <p>
        Claim {latest.claim_id}, received {dateOnly(latest.received)}
        {care ? `, ${care}` : ""}: <strong>{memberOutcome(latest.outcome).label}</strong>.
      </p>
      <p className="mt-1">{latest.message}</p>
      <Link to={`/member/claims/${encodeURIComponent(latest.claim_id)}`} className="mt-2 inline-block font-semibold text-link underline">
        Open the claim
      </Link>
    </>
  );
}

function Visits({ benefits }: { benefits: MemberBenefits }) {
  if (benefits.visits.length === 0) return <p>Your plan has no services with a yearly visit limit.</p>;
  return (
    <>
      <ul className="list-disc pl-5">
        {benefits.visits.map((v) => (
          <li key={v.benefit_category}>
            {benefitCategory(v.benefit_category)}: {v.visits_used} of {v.visit_limit} visits used this benefit year.
          </li>
        ))}
      </ul>
      <Link to="/member/benefits" className="mt-2 inline-block font-semibold text-link underline">
        See My benefits
      </Link>
    </>
  );
}

function OutOfPocket({ benefits }: { benefits: MemberBenefits }) {
  return (
    <>
      <ul className="list-disc pl-5">
        {benefits.networks.map((n) => (
          <li key={n.network}>
            {NETWORKS[n.network] ?? n.network}: you have spent {money(n.oop_met_cents)} of your {money(n.oop_max_cents)}{" "}
            out-of-pocket maximum
            {n.oop_left_cents > 0
              ? `; ${money(n.oop_left_cents)} to go before you pay no more cost share for covered care.`
              : ": reached for this benefit year."}
          </li>
        ))}
      </ul>
      <p className="mt-1">A claim still being processed is not counted yet.</p>
      <Link to="/member/benefits" className="mt-2 inline-block font-semibold text-link underline">
        See My benefits
      </Link>
    </>
  );
}

function PlanAnswer() {
  return (
    <>
      <p>
        Your plan's summary of benefits and coverage lists each kind of care, what you pay for it in and out of network,
        what needs approval first and what is not covered.
      </p>
      <Link to="/member/plan" className="mt-2 inline-block font-semibold text-link underline">
        Open My plan
      </Link>
    </>
  );
}

function AppealAnswer({ claims }: { claims: MemberClaim[] }) {
  const open = claims.filter((c) => c.can_appeal);
  return (
    <>
      <p>
        Yes. A denied claim can be appealed once: say what the decision missed, and a reviewer who did not deny it
        decides it again.
      </p>
      {open.length === 0 ? (
        <p className="mt-1">None of your claims can be appealed right now.</p>
      ) : (
        <ul className="mt-1 list-disc pl-5">
          {open.map((c) => (
            <li key={c.claim_id}>
              <Link to={`/member/claims/${encodeURIComponent(c.claim_id)}`} className="font-semibold text-link underline">
                Claim {c.claim_id}
              </Link>{" "}
              can be appealed.
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function Unknown() {
  return (
    <>
      <p>I can answer these from your records:</p>
      <ul className="mt-1 list-disc pl-5">
        {QUESTIONS.map((q) => (
          <li key={q.id}>{q.text}</li>
        ))}
      </ul>
      <p className="mt-1">For anything else, call the number on your member card.</p>
    </>
  );
}

function Answer({ question }: { question: Question }) {
  const benefits = useMemberBenefits();
  const claims = useMemberClaims();
  if (question === "unknown") return <Unknown />;
  if (question === "plan") return <PlanAnswer />;
  const query = question === "latest" || question === "appeal" ? claims : benefits;
  if (query.isPending) return <p className="text-ink-muted">Looking that up…</p>;
  if (query.error) return <p>That answer is not available right now. Try again in a moment.</p>;
  if (question === "latest") return <Latest claims={claims.data ?? []} />;
  if (question === "appeal") return <AppealAnswer claims={claims.data ?? []} />;
  if (question === "oop") return <OutOfPocket benefits={benefits.data!} />;
  return question === "deductible" ? <Deductible benefits={benefits.data!} /> : <Visits benefits={benefits.data!} />;
}

interface Asked {
  key: number;
  question: Question;
  text: string;
}

export function MemberAssistant() {
  const [asked, setAsked] = useState<Asked[]>([]);
  const [typed, setTyped] = useState("");
  const ask = (question: Question, text: string) =>
    setAsked((before) => [...before, { key: (before.at(-1)?.key ?? 0) + 1, question, text }]);
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button size="lg" className="fixed right-4 bottom-4 z-30 h-12 rounded-full px-5 shadow-lg print:hidden md:right-8 md:bottom-8">
          <MessageCircleQuestion aria-hidden className="size-5" />
          Ask about your plan
          <span className="rounded-full bg-white/20 px-2 py-0.5 text-[12px]">Preview</span>
        </Button>
      </SheetTrigger>
      <SheetContent side="right" className="w-full gap-0 sm:max-w-md">
        <SheetHeader className="border-b border-rules">
          <SheetTitle className="flex items-center gap-2 font-heading text-[22px] font-bold text-ink-strong">
            Plan assistant <PlainBadge>Preview</PlainBadge>
          </SheetTitle>
          <SheetDescription>
            Quick answers from your own plan and claims. Choose a question or type your own.
          </SheetDescription>
        </SheetHeader>
        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
          <section aria-label="Quick questions" className="flex flex-col gap-2">
            {QUESTIONS.map((q) => (
              <Button
                key={q.id}
                variant="outline"
                className="h-auto justify-start py-2.5 text-left whitespace-normal"
                onClick={() => ask(q.id, q.text)}
              >
                {q.text}
              </Button>
            ))}
          </section>
          <ol aria-label="Answers" aria-live="polite" className="flex flex-col gap-3">
            {asked.map((item) => (
              <li key={item.key} className="flex flex-col gap-2">
                <p className="ml-8 self-end rounded-lg bg-brand-tint px-3 py-2 break-words text-ink-strong">{item.text}</p>
                <div className="mr-8 rounded-lg border border-rules bg-white px-3 py-2 text-[15px] leading-6">
                  <p className="mb-1 text-[12px] font-semibold tracking-wide text-ink-muted uppercase">Plan assistant</p>
                  <Answer question={item.question} />
                </div>
              </li>
            ))}
          </ol>
        </div>
        <form
          className="border-t border-rules p-4"
          onSubmit={(event) => {
            event.preventDefault();
            const text = typed.trim();
            if (!text) return;
            ask(matchQuestion(text), text);
            setTyped("");
          }}
        >
          <label htmlFor="assistant-question" className="mb-2 block text-[14px] font-semibold">
            Ask in your own words
          </label>
          <div className="flex gap-2">
            <Input
              id="assistant-question"
              value={typed}
              maxLength={300}
              placeholder="For example: how much is left on my deductible?"
              className="h-10"
              onChange={(event) => setTyped(event.target.value)}
            />
            <Button type="submit" disabled={!typed.trim()} aria-label="Send">
              <Send aria-hidden />
            </Button>
          </div>
          <p className="mt-2 text-[13px] text-ink-muted">
            Your question is matched to the ones above by its words, and answered straight from your plan's records; no
            AI model is used.
          </p>
        </form>
      </SheetContent>
    </Sheet>
  );
}
