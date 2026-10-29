// Model metrics (admin): model v3 against v2 on four sets (each measured on one machine, named),
// models v1, v2 and E4B on the same 300 synthetic v2 test claims side by side, the per-class
// scores, the evidence-guard rows, and what else the results file records. Every
// number comes from GET /v1/metrics/evaluation or GET /v1/metrics/results; "not measured" and "not
// applicable" are shown exactly as the API returns them.

import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";

import { ApiError } from "@/api/client";
import { useEvaluation, useResults } from "@/api/hooks";
import type { GuardRow, ModelRow, Results, V3Set } from "@/api/types";
import { PageTitle, Section } from "@/components/Layout";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/States";
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { percent } from "@/lib/format";
import { DECISION } from "@/lib/labels";

/** "claimsense-decision:e4b" -> "e4b": the key the results file's guard rows use. */
const keyOf = (model: string) => model.replace("claimsense-decision:", "");
const nameOf = (model: string) => (keyOf(model) === "e4b" ? "Model E4B" : `Model ${keyOf(model)}`);
const three = (value: number | null | undefined) => (value === null || value === undefined ? "—" : value.toFixed(3));
const seconds = (ms: number) => `${(ms / 1000).toFixed(1)} s`;

function Target({ met }: { met: boolean }) {
  return (
    <span className={`block text-[13px] font-semibold ${met ? "text-approve" : "text-deny"}`}>
      {met ? "Target met" : "Below target"}
    </span>
  );
}

function SideBySide({ models, guard, target }: { models: ModelRow[]; guard: GuardRow[]; target: number }) {
  const wrong = (model: string) => guard.find((g) => g.model === keyOf(model))?.wrong_approvals;
  const rows: { label: string; cell: (m: ModelRow) => React.ReactNode }[] = [
    { label: "Valid output", cell: (m) => percent(m.valid_output) },
    { label: "Line accuracy", cell: (m) => three(m.line_accuracy) },
    {
      label: `Macro-F1 (target ${target.toFixed(2)})`,
      cell: (m) => (
        <>
          {three(m.macro_f1)}
          <Target met={m.macro_f1 >= target} />
        </>
      ),
    },
    { label: "Criterion accuracy", cell: (m) => three(m.criterion_accuracy) },
    { label: "Deny precision", cell: (m) => three(m.deny_precision) },
    { label: "Wrong approvals", cell: (m) => wrong(m.model) ?? "—" },
    { label: "Median time per claim", cell: (m) => seconds(m.median_ms_per_claim) },
    { label: "95th percentile time", cell: (m) => seconds(m.p95_ms_per_claim) },
  ];
  return (
    <div className="overflow-x-auto surface rounded-lg">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Measure</TableHead>
            {models.map((m) => (
              <TableHead key={m.model} className="text-right">
                {nameOf(m.model)}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.label}>
              <TableCell className="font-semibold">{row.label}</TableCell>
              {models.map((m) => (
                <TableCell key={m.model} className="text-right whitespace-nowrap tabular-nums">
                  {row.cell(m)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function V3AgainstV2({ sets }: { sets: V3Set[] }) {
  const interval = (ci: [number, number] | null) =>
    ci ? `${ci[0] >= 0 ? "+" : ""}${ci[0].toFixed(3)} to ${ci[1] >= 0 ? "+" : ""}${ci[1].toFixed(3)}` : "—";
  return (
    <div className="overflow-x-auto surface rounded-lg">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Set</TableHead>
            <TableHead>Measured on</TableHead>
            <TableHead className="text-right">Claims</TableHead>
            <TableHead className="text-right">v2 macro-F1</TableHead>
            <TableHead className="text-right">v3 macro-F1</TableHead>
            <TableHead className="text-right">v3 − v2, 95% interval</TableHead>
            <TableHead className="text-right">v3 valid output</TableHead>
            <TableHead className="text-right">v3 deny precision</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sets.map((s) => (
            <TableRow key={`${s.title} ${s.machine}`}>
              <TableCell>
                <span className="font-semibold">{s.title}</span>
                <span className="block text-[13px] text-ink-muted">{s.notes}</span>
              </TableCell>
              <TableCell>{s.machine}</TableCell>
              <TableCell className="text-right tabular-nums">{s.claims}</TableCell>
              <TableCell className="text-right tabular-nums">{three(s.v2.macro_f1)}</TableCell>
              <TableCell className="text-right tabular-nums font-semibold">{three(s.v3.macro_f1)}</TableCell>
              <TableCell className="text-right tabular-nums whitespace-nowrap">{interval(s.macro_f1_difference_ci95)}</TableCell>
              <TableCell className="text-right tabular-nums">{percent(s.v3.valid_output)}</TableCell>
              <TableCell className="text-right tabular-nums">{three(s.v3.deny_precision)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function PerClass({ models }: { models: ModelRow[] }) {
  return (
    <div className="overflow-x-auto surface rounded-lg">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Model</TableHead>
            <TableHead>Decision</TableHead>
            <TableHead className="text-right">Precision</TableHead>
            <TableHead className="text-right">Recall</TableHead>
            <TableHead className="text-right">F1</TableHead>
            <TableHead className="text-right">Lines</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {models.flatMap((m) =>
            (["APPROVE", "PEND", "DENY"] as const)
              .filter((d) => m.per_class[d])
              .map((d) => {
                const s = m.per_class[d]!;
                return (
                  <TableRow key={`${m.model}-${d}`}>
                    <TableCell className="font-semibold">{nameOf(m.model)}</TableCell>
                    <TableCell>{DECISION[d].label}</TableCell>
                    <TableCell className="text-right tabular-nums">{three(s.precision)}</TableCell>
                    <TableCell className="text-right tabular-nums">{three(s.recall)}</TableCell>
                    <TableCell className="text-right tabular-nums">{three(s.f1)}</TableCell>
                    <TableCell className="text-right tabular-nums">{s.support ?? "—"}</TableCell>
                  </TableRow>
                );
              }),
          )}
        </TableBody>
      </Table>
    </div>
  );
}

function GuardRows({ rows }: { rows: GuardRow[] }) {
  return (
    <div className="overflow-x-auto surface rounded-lg">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Answers</TableHead>
            <TableHead className="text-right">Line accuracy</TableHead>
            <TableHead className="text-right">Macro-F1</TableHead>
            <TableHead className="text-right">Deny precision</TableHead>
            <TableHead className="text-right">Wrong approvals</TableHead>
            <TableHead className="text-right">Wrong denials</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((g) => (
            <TableRow key={g.model}>
              <TableCell className="font-semibold">
                {g.model.replace(/^(\w+)/, (k) => (k === "e4b" ? "Model E4B" : `Model ${k}`))}
              </TableCell>
              <TableCell className="text-right tabular-nums">{three(g.line_accuracy)}</TableCell>
              <TableCell className="text-right tabular-nums">{three(g.macro_f1)}</TableCell>
              <TableCell className="text-right tabular-nums">{three(g.deny_precision)}</TableCell>
              <TableCell className="text-right tabular-nums">{g.wrong_approvals}</TableCell>
              <TableCell className="text-right tabular-nums">{g.wrong_denials}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function AlsoRecorded({ results }: { results: Results }) {
  const stages = Object.entries(results.latency_per_stage_ms).filter(
    (entry): entry is [string, { claims: number; median: number; max: number }] =>
      typeof entry[1] === "object" && entry[1] !== null,
  );
  const extraction = results.extraction;
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <dl className="surface rounded-lg px-4 py-2">
        {[
          ["Retrieval recall@3", results.retrieval_recall_at_3],
          ["Reviewer agreement", results.reviewer_agreement],
          ["Review time", results.review_time],
          [
            "Scanned-form field accuracy",
            typeof extraction === "string"
              ? extraction
              : `${percent(extraction.field_accuracy)} on ${extraction.fields.toLocaleString("en-US")} fields of ${extraction.held_out_claims} held-out scans (target ${percent(extraction.target)})`,
          ],
          ...Object.entries(results.rules_and_calculator).map(([suite, c]) => [
            `Golden ${suite}`,
            `${c.passed} passed, ${c.failed + c.error} failed, ${c.skipped} skipped`,
          ]),
        ].map(([label, value]) => (
          <div key={label} className="grid gap-x-4 border-b border-rules py-2 last:border-b-0 sm:grid-cols-[14rem_1fr]">
            <dt className="font-semibold">{label}</dt>
            <dd className="text-ink-muted">{value}</dd>
          </div>
        ))}
      </dl>
      {stages.length > 0 && (
        <div className="overflow-x-auto surface rounded-lg">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Stage</TableHead>
                <TableHead className="text-right">Claims</TableHead>
                <TableHead className="text-right">Median</TableHead>
                <TableHead className="text-right">Slowest</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {stages.map(([stage, v]) => (
                <TableRow key={stage}>
                  <TableCell>{stage.replace("_ms", "").replace("duration", "whole claim")}</TableCell>
                  <TableCell className="text-right tabular-nums">{v.claims}</TableCell>
                  <TableCell className="text-right tabular-nums">{v.median} ms</TableCell>
                  <TableCell className="text-right tabular-nums">{v.max} ms</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <p className="border-t border-rules px-4 py-2 text-[13px] text-ink-muted">
            Time per pipeline stage, from the claims the API processed ({results.latency_per_stage_ms.source}).
          </p>
        </div>
      )}
    </div>
  );
}

// v1 muted slate, v2 blue (the demo model), E4B cyan: each 3:1 or more against the panel.
const SHADES = ["#7C8AA5", "#7B93FF", "#5FD8EA"];

function Chart({ models }: { models: ModelRow[] }) {
  const measures: { key: keyof ModelRow; label: string }[] = [
    { key: "valid_output", label: "Valid output" },
    { key: "line_accuracy", label: "Line accuracy" },
    { key: "macro_f1", label: "Macro-F1" },
    { key: "criterion_accuracy", label: "Criterion accuracy" },
    { key: "deny_precision", label: "Deny precision" },
  ];
  const config: ChartConfig = Object.fromEntries(
    models.map((m, i) => [keyOf(m.model), { label: nameOf(m.model), color: SHADES[i % SHADES.length] }]),
  );
  const data = measures.map((measure) => ({
    measure: measure.label,
    ...Object.fromEntries(models.map((m) => [keyOf(m.model), m[measure.key]])),
  }));
  return (
    <div className="mt-6 surface rounded-lg p-4">
      <h3 className="mb-2 font-semibold">The same measures as bars (0 to 1)</h3>
      <ChartContainer config={config} className="aspect-auto h-72 w-full">
        <BarChart data={data} margin={{ left: -16, right: 8 }}>
          <CartesianGrid vertical={false} stroke="rgb(255 255 255 / 0.08)" />
          <XAxis dataKey="measure" tickLine={false} axisLine={false} interval={0} tick={{ fontSize: 12, fill: "#A9B4CA" }} />
          <YAxis domain={[0, 1]} tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "#A9B4CA" }} />
          <ChartTooltip content={<ChartTooltipContent />} />
          <ChartLegend content={<ChartLegendContent />} />
          {Object.keys(config).map((key) => (
            <Bar key={key} dataKey={key} fill={`var(--color-${key})`} radius={[4, 4, 0, 0]} isAnimationActive={false} />
          ))}
        </BarChart>
      </ChartContainer>
    </div>
  );
}

export function Metrics() {
  const evaluation = useEvaluation();
  const results = useResults();
  const noResults = results.error instanceof ApiError && results.error.status === 404;
  if (evaluation.isPending) return <Skeleton lines={8} />;
  if (evaluation.error) return <ErrorNotice error={evaluation.error} onRetry={() => void evaluation.refetch()} />;
  const { models, macro_f1_target, v3_sets } = evaluation.data;
  const guard = results.data?.evidence_guard ?? [];
  return (
    <>
      <PageTitle
        title="Model metrics"
        hint="v3 is the model the demo uses: first against v2 on four sets of synthetic claims, then models v1, v2 and E4B on the same 300 v2 test claims. Line decisions are derived from the criteria, as the pipeline derives them."
      />
      {v3_sets.length > 0 && (
        <Section title="Model v3 against v2">
          <V3AgainstV2 sets={v3_sets} />
          <p className="mt-3 max-w-[72ch] text-[13px] text-ink-muted">
            Both models on each set, on the machine named, with the evidence guard as the pipeline runs (notes stuck in a
            loop left out). An interval above zero means v3 is better on that set beyond chance. From docs/results-v3.md.
          </p>
        </Section>
      )}
      <Section title="Side by side">
        {models.length === 0 ? (
          <EmptyState title="No evaluation results yet">
            Run uv run python -m training.evaluate.compare_v2 to evaluate the models.
          </EmptyState>
        ) : (
          <>
            <SideBySide models={models} guard={guard} target={macro_f1_target} />
            <p className="mt-3 max-w-[72ch] text-[13px] text-ink-muted">
              Wrong approvals: lines the model would approve that should be pended or denied, as each model was
              evaluated (v1 and v2 without the evidence guard, E4B with it). Every recommendation still goes to a
              reviewer.
            </p>
            <Chart models={models} />
          </>
        )}
      </Section>
      {models.length > 0 && (
        <Section title="By decision">
          <PerClass models={models} />
        </Section>
      )}
      <Section title="Evidence guard">
        {results.isPending ? (
          <Skeleton lines={4} />
        ) : noResults ? (
          <EmptyState title="No results file yet">Run make results to write it.</EmptyState>
        ) : results.error ? (
          <ErrorNotice error={results.error} onRetry={() => void results.refetch()} />
        ) : (
          <>
            <p className="mb-3 max-w-[72ch] text-ink-muted">
              The same stored answers, without and with the evidence guard, which turns a met criterion whose quote is
              not in the note into not documented (D-EVID-1).
            </p>
            <GuardRows rows={guard} />
          </>
        )}
      </Section>
      {results.data && (
        <Section title="Also recorded">
          <AlsoRecorded results={results.data} />
        </Section>
      )}
    </>
  );
}
