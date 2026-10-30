// The member's plan assistant, as a preview (D-MEM-4): a button on every member page opens a panel
// with three quick questions answered from the member's own records, as the member pages already
// read them (GET /v1/member/benefits and /v1/member/claims). No model is called: each answer is
// the API's values in a fixed sentence, formatted only; nothing is computed (no amount or visit
// count is added or subtracted, D-MEM-3). Asking in one's own words is shown, disabled, as the
// later phase.

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

type Question = "deductible" | "latest" | "visits";

const QUESTIONS: { id: Question; text: string }[] = [
  { id: "deductible", text: "How much of my deductible have I met?" },
  { id: "latest", text: "What is the status of my latest claim?" },
  { id: "visits", text: "How many visits have I used this year?" },
];

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

function Answer({ question }: { question: Question }) {
  const benefits = useMemberBenefits();
  const claims = useMemberClaims();
  const query = question === "latest" ? claims : benefits;
  if (query.isPending) return <p className="text-ink-muted">Looking that up…</p>;
  if (query.error) return <p>That answer is not available right now. Try again in a moment.</p>;
  if (question === "latest") return <Latest claims={claims.data ?? []} />;
  return question === "deductible" ? <Deductible benefits={benefits.data!} /> : <Visits benefits={benefits.data!} />;
}

export function MemberAssistant() {
  const [asked, setAsked] = useState<Question[]>([]);
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
            Quick answers from your own plan and claims. Asking in your own words comes in a later phase.
          </SheetDescription>
        </SheetHeader>
        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
          <section aria-label="Quick questions" className="flex flex-col gap-2">
            {QUESTIONS.map((q) => (
              <Button
                key={q.id}
                variant="outline"
                className="h-auto justify-start py-2.5 text-left whitespace-normal"
                onClick={() => setAsked((before) => [...before.filter((id) => id !== q.id), q.id])}
              >
                {q.text}
              </Button>
            ))}
          </section>
          <ol aria-label="Answers" aria-live="polite" className="flex flex-col gap-3">
            {asked.map((id) => (
              <li key={id} className="flex flex-col gap-2">
                <p className="ml-8 self-end rounded-lg bg-brand-tint px-3 py-2 text-ink-strong">
                  {QUESTIONS.find((q) => q.id === id)!.text}
                </p>
                <div className="mr-8 rounded-lg border border-rules bg-white px-3 py-2 text-[15px] leading-6">
                  <p className="mb-1 text-[12px] font-semibold tracking-wide text-ink-muted uppercase">Plan assistant</p>
                  <Answer question={id} />
                </div>
              </li>
            ))}
          </ol>
        </div>
        <form className="border-t border-rules p-4" onSubmit={(event) => event.preventDefault()}>
          <label htmlFor="assistant-question" className="mb-2 block text-[14px] font-semibold">
            Ask in your own words
          </label>
          <div className="flex gap-2">
            <Input id="assistant-question" disabled placeholder="Coming in a later phase" className="h-10" />
            <Button type="submit" disabled aria-label="Send">
              <Send aria-hidden />
            </Button>
          </div>
          <p className="mt-2 text-[13px] text-ink-muted">
            These answers come straight from your plan's records; no AI model is used in this preview.
          </p>
        </form>
      </SheetContent>
    </Sheet>
  );
}
