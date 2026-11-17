// Review quality (admin, D-QLT-1): how reviewers use the model's recommendations, from every review
// on file: how many model lines they accepted, the model's decision against the final one, by
// review tier, reviewer and coverage policy, how long reviews take, the criteria reviewers corrected
// (D-FBK-1) and the appeals (D-APL-1). Rates are the API's basis points, formatted only. Downloads:
// the policy table as CSV, and the reviewed claims as training examples (JSON lines) for the next
// fine-tune, the reviewers' corrections applied.

import { Download } from "lucide-react";

import { useQuality } from "@/api/hooks";
import type { QualityTally } from "@/api/types";
import { BlurFade, NumberTicker, Spotlight } from "@/components/fx";
import { PageTitle, Section } from "@/components/Layout";
import { CsvButton } from "@/components/ListTools";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { basisPoints, duration } from "@/lib/format";
import { DECISION, TIER } from "@/lib/labels";

const DECISIONS = ["APPROVE", "PEND", "DENY"] as const;

function Stat({ label, value, hint }: { label: string; value: string | number; hint: string }) {
  return (
    <Spotlight className="h-full px-5 py-4">
      <p className="text-[14px] text-ink-muted">{label}</p>
      <p className="mt-2 font-heading text-[30px] leading-9 font-bold text-ink-strong tabular-nums">
        {typeof value === "number" ? <NumberTicker value={value} /> : value}
      </p>
      <p className="mt-1 text-[13px] text-ink-muted">{hint}</p>
    </Spotlight>
  );
}

/** The columns the breakdowns share; a policy's lines only (reviews and times are per claim). */
function TallyCells({ tally, lines = false }: { tally: QualityTally; lines?: boolean }) {
  return (
    <>
      {!lines && <TableCell className="text-right tabular-nums">{tally.reviews}</TableCell>}
      <TableCell className="text-right tabular-nums">{tally.lines}</TableCell>
      <TableCell className="text-right tabular-nums">{tally.overridden}</TableCell>
      <TableCell className="text-right tabular-nums">{basisPoints(tally.override_rate_bp)}</TableCell>
      {!lines && <TableCell className="text-right tabular-nums">{duration(tally.review_seconds.median)}</TableCell>}
    </>
  );
}

function TallyHead({ first, lines = false }: { first: string; lines?: boolean }) {
  return (
    <TableHeader>
      <TableRow>
        <TableHead>{first}</TableHead>
        {!lines && <TableHead className="text-right">Reviews</TableHead>}
        <TableHead className="text-right">Model lines</TableHead>
        <TableHead className="text-right">Changed</TableHead>
        <TableHead className="text-right">Changed rate</TableHead>
        {!lines && <TableHead className="text-right">Median time</TableHead>}
      </TableRow>
    </TableHeader>
  );
}

export function ReviewQuality() {
  const quality = useQuality();
  return (
    <>
      <PageTitle
        title="Review quality"
        hint="How reviewers use the model's recommendations, from every review on file in this demo."
        actions={
          <Button asChild variant="outline">
            <a href="/v1/metrics/training-examples" download="reviewer-examples.jsonl">
              <Download aria-hidden /> Download training examples
            </a>
          </Button>
        }
      />
      {quality.isPending ? (
        <Skeleton lines={8} />
      ) : quality.error ? (
        <ErrorNotice error={quality.error} onRetry={() => void quality.refetch()} />
      ) : quality.data.overall.reviews === 0 ? (
        <EmptyState title="No reviews yet">The numbers appear once a reviewer finalizes a claim.</EmptyState>
      ) : (
        <div className="space-y-8">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {[
              {
                label: "Model lines accepted",
                value: basisPoints(quality.data.acceptance_rate_bp),
                hint: `${quality.data.overall.lines - quality.data.overall.overridden} of ${quality.data.overall.lines} lines kept as recommended`,
              },
              { label: "Reviews", value: quality.data.overall.reviews, hint: "Appeals count as a second review" },
              {
                label: "Review time, median",
                value: duration(quality.data.overall.review_seconds.median),
                hint: `9 in 10 within ${duration(quality.data.overall.review_seconds.p90)}`,
              },
              {
                label: "Criteria corrected",
                value: quality.data.feedback.criteria,
                hint: `On ${quality.data.feedback.lines} line${quality.data.feedback.lines === 1 ? "" : "s"}, for the next fine-tune`,
              },
            ].map((stat, i) => (
              <BlurFade key={stat.label} delay={i * 0.05}>
                <Stat {...stat} />
              </BlurFade>
            ))}
          </div>

          <Section title="The model's decision against the final one">
            <p className="mb-3 text-[14px] text-ink-muted">
              Lines the model recommended (rows) and how the reviewer finalized them (columns). The diagonal is
              agreement.
            </p>
            <div className="surface overflow-x-auto rounded-lg">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Model recommended</TableHead>
                    {DECISIONS.map((d) => (
                      <TableHead key={d} className="text-right">
                        Final: {DECISION[d].label.toLowerCase()}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {DECISIONS.filter((d) => quality.data.matrix[d]).map((model) => (
                    <TableRow key={model}>
                      <TableCell className="font-semibold">{DECISION[model].label}</TableCell>
                      {DECISIONS.map((final) => (
                        <TableCell
                          key={final}
                          className={`text-right tabular-nums ${final === model ? "font-semibold" : ""}`}
                        >
                          {quality.data.matrix[model]?.[final] ?? 0}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </Section>

          <Section title="By review tier">
            <div className="surface overflow-x-auto rounded-lg">
              <Table>
                <TallyHead first="Tier" />
                <TableBody>
                  {Object.entries(quality.data.by_tier).map(([tier, tally]) => (
                    <TableRow key={tier}>
                      <TableCell>{TIER[tier as keyof typeof TIER]?.label ?? "No tier"}</TableCell>
                      <TallyCells tally={tally} />
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </Section>

          <Section title="By reviewer">
            <div className="surface overflow-x-auto rounded-lg">
              <Table>
                <TallyHead first="Reviewer" />
                <TableBody>
                  {quality.data.by_reviewer.map((row) => (
                    <TableRow key={row.reviewer}>
                      <TableCell>{row.reviewer}</TableCell>
                      <TallyCells tally={row} />
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </Section>

          <Section
            title="By coverage policy"
            aside={
              <CsvButton
                rows={quality.data.by_policy}
                fileName="review-quality-by-policy.csv"
                columns={[
                  { header: "Policy", value: (r) => r.policy_id },
                  { header: "Title", value: (r) => r.title ?? "" },
                  { header: "Model lines", value: (r) => r.lines },
                  { header: "Changed", value: (r) => r.overridden },
                  { header: "Changed rate (basis points)", value: (r) => r.override_rate_bp ?? "" },
                ]}
              />
            }
          >
            <p className="mb-3 text-[14px] text-ink-muted">Most changed first: where the model needs work.</p>
            <div className="surface overflow-x-auto rounded-lg">
              <Table>
                <TallyHead first="Policy" lines />
                <TableBody>
                  {quality.data.by_policy.map((row) => (
                    <TableRow key={row.policy_id}>
                      <TableCell className="min-w-56">
                        {row.policy_id === "none" ? "No coverage policy" : row.policy_id}
                        {row.title && <div className="text-[13px] text-ink-muted">{row.title}</div>}
                      </TableCell>
                      <TallyCells tally={row} lines />
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </Section>

          <Section title="Appeals">
            <dl className="surface grid gap-4 rounded-lg p-5 sm:grid-cols-3">
              <div>
                <dt className="text-[14px] text-ink-muted">Waiting for a reviewer</dt>
                <dd className="text-[22px] font-semibold tabular-nums">{quality.data.appeals.open}</dd>
              </div>
              <div>
                <dt className="text-[14px] text-ink-muted">Decision stood</dt>
                <dd className="text-[22px] font-semibold tabular-nums">{quality.data.appeals.upheld}</dd>
              </div>
              <div>
                <dt className="text-[14px] text-ink-muted">Decision changed</dt>
                <dd className="text-[22px] font-semibold tabular-nums">{quality.data.appeals.changed}</dd>
              </div>
            </dl>
          </Section>
        </div>
      )}
    </>
  );
}
