// The coverage policy library (providers, reviewers and admins, D-POL-9): the policies the pipeline
// checks claims against, each with its procedure codes and plain names and every criterion in its
// own words, with its type and source. Search by procedure code or words (kept in the URL), so a
// provider can see what a service needs before writing the notes. Read only.

import { BookOpen, Search } from "lucide-react";
import { useId } from "react";
import { useSearchParams } from "react-router";

import { usePolicies, usePolicy } from "@/api/hooks";
import type { PolicySummary } from "@/api/types";
import { PageTitle, Panel } from "@/components/Layout";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { dateOnly } from "@/lib/format";

const TYPES: Record<string, { label: string; hint: string }> = {
  requirement: { label: "Needed", hint: "The notes must show it" },
  conditional: { label: "Only when it applies", hint: "Needed in some situations" },
  exclusion: { label: "Not covered when", hint: "The service is not covered when this is so" },
};

function found(policy: PolicySummary, query: string): boolean {
  const wanted = query.trim().toLowerCase();
  if (!wanted) return true;
  return (
    policy.title.toLowerCase().includes(wanted) ||
    policy.policy_id.toLowerCase().includes(wanted) ||
    policy.codes.some((c) => c.code.toLowerCase().includes(wanted) || (c.name ?? "").toLowerCase().includes(wanted))
  );
}

function Detail({ policyId }: { policyId: string }) {
  const policy = usePolicy(policyId);
  if (policy.isPending) return <Skeleton lines={6} />;
  if (policy.error) return <ErrorNotice error={policy.error} onRetry={() => void policy.refetch()} />;
  const p = policy.data;
  const groups = ["requirement", "conditional", "exclusion", ""].map((type) => ({
    type,
    items: p.items.filter((item) => (item.criterion_type ?? "") === type),
  }));
  return (
    <Panel className="p-5">
      <p className="text-[13px] text-ink-muted">
        {p.policy_id} · billing article {p.billing_article} · effective {dateOnly(p.effective_date)}
      </p>
      <h2 className="mt-1 text-[22px] leading-8 font-bold">{p.title}</h2>
      <ul className="mt-3 flex flex-wrap gap-2">
        {p.codes.map((c) => (
          <li
            key={c.code}
            className="max-w-full rounded-2xl border border-rules bg-subtle px-2.5 py-0.5 text-[13px] font-semibold break-words text-ink"
          >
            {c.code}
            {c.name ? ` · ${c.name}` : ""}
          </li>
        ))}
      </ul>
      {groups
        .filter((g) => g.items.length > 0)
        .map((group) => (
          <section key={group.type || "untyped"} className="mt-5" aria-label={TYPES[group.type]?.label ?? "Criteria"}>
            <h3 className="font-semibold">{TYPES[group.type]?.label ?? "Criteria"}</h3>
            {TYPES[group.type] && <p className="text-[13px] text-ink-muted">{TYPES[group.type]!.hint}.</p>}
            <ul className="mt-2 divide-y divide-rules">
              {group.items.map((item) => (
                <li key={item.criterion_id} className="py-3">
                  <p>{item.text}</p>
                  <p className="mt-1 text-[13px] text-ink-muted">
                    {item.criterion_id}
                    {item.applies_to.length ? ` · for ${item.applies_to.join(", ")}` : ""}
                    {item.group ? ` · one of group ${item.group}` : ""} · {item.source}
                  </p>
                </li>
              ))}
            </ul>
          </section>
        ))}
      <p className="mt-5 text-[13px] text-ink-muted">Sources: {p.sources.join("; ")}</p>
    </Panel>
  );
}

export function Policies() {
  const policies = usePolicies();
  const [params, setParams] = useSearchParams();
  const query = params.get("q") ?? "";
  const chosen = params.get("policy");
  const searchId = useId();
  const set = (key: string, value: string | null) =>
    setParams(
      (now) => {
        const next = new URLSearchParams(now);
        if (value) next.set(key, value);
        else next.delete(key);
        return next;
      },
      { replace: key === "q" },
    );
  const shown = (policies.data ?? []).filter((p) => found(p, query));
  return (
    <>
      <PageTitle
        title="Coverage policies"
        hint="What each coverage policy asks the clinical notes to show, in its own words. Look up a procedure code before you write the notes."
      />
      {policies.isPending ? (
        <Skeleton lines={6} />
      ) : policies.error ? (
        <ErrorNotice error={policies.error} onRetry={() => void policies.refetch()} />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          {/* On a phone or tablet an open policy takes the list's place ("Back to the list"). */}
          <div className={`min-w-0 ${chosen ? "hidden lg:block" : ""}`}>
            <label className="mb-3 grid gap-1.5 text-[13px] font-semibold" htmlFor={searchId}>
              Search by procedure code or words
              <span className="relative">
                <Search aria-hidden className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-muted" />
                <Input
                  id={searchId}
                  value={query}
                  placeholder="For example 70551 or MRI"
                  className="h-10 bg-paper pl-9 text-[15px] font-normal"
                  onChange={(event) => set("q", event.target.value)}
                />
              </span>
            </label>
            <p className="mb-2 text-[13px] text-ink-muted" aria-live="polite">
              {shown.length} polic{shown.length === 1 ? "y" : "ies"}
            </p>
            {shown.length === 0 ? (
              <EmptyState title="No policy matches">
                A code without a policy has no coverage conditions: the claim checks and the reviewer decide it.
              </EmptyState>
            ) : (
              <ul aria-label="Policies" className="grid gap-2">
                {shown.map((p) => (
                  <li key={p.policy_id}>
                    <button
                      type="button"
                      aria-pressed={chosen === p.policy_id}
                      onClick={() => set("policy", p.policy_id)}
                      className={`surface w-full rounded-lg p-3 text-left transition-colors hover:bg-brand-tint/60 ${chosen === p.policy_id ? "ring-2 ring-primary" : ""}`}
                    >
                      <span className="block font-semibold">{p.title}</span>
                      <span className="block text-[13px] text-ink-muted">
                        {p.codes.map((c) => c.code).join(", ")} · {p.criteria} criteri{p.criteria === 1 ? "on" : "a"}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="min-w-0 lg:sticky lg:top-20 lg:self-start">
            {chosen ? (
              <>
                <Button variant="ghost" className="mb-2 lg:hidden" onClick={() => set("policy", null)}>
                  Back to the list
                </Button>
                <Detail policyId={chosen} />
              </>
            ) : (
              <EmptyState title="Choose a policy">
                <BookOpen aria-hidden className="mx-auto mb-2 size-6 text-ink-muted" />
                Its criteria show here: what the notes must show, what applies only sometimes, and when the service is
                not covered.
              </EmptyState>
            )}
          </div>
        </div>
      )}
    </>
  );
}
