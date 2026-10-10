// Metrics: model v1 and model v2 on the same 300 synthetic v2 test claims, one grouped bar chart,
// where v2 goes wrong, and the OCR field accuracy, each against its target.

import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";

import { useEvaluation } from "@/api/hooks";
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

function Target({ met }: { met: boolean }) {
  return (
    <span className={`ml-2 text-[13px] font-semibold ${met ? "text-approve" : "text-deny"}`}>
      {met ? "Target met" : "Below target"}
    </span>
  );
}

const MEASURES: { key: "valid_output" | "line_accuracy" | "macro_f1" | "criterion_accuracy" | "deny_precision"; label: string }[] = [
  { key: "valid_output", label: "Valid output" },
  { key: "line_accuracy", label: "Line accuracy" },
  { key: "macro_f1", label: "Macro-F1" },
  { key: "criterion_accuracy", label: "Criterion accuracy" },
  { key: "deny_precision", label: "Deny precision" },
];

export function Metrics() {
  const evaluation = useEvaluation();
  if (evaluation.isPending) return <Skeleton lines={6} />;
  if (evaluation.error) return <ErrorNotice error={evaluation.error} onRetry={() => void evaluation.refetch()} />;
  const { models, macro_f1_target, ocr, ocr_target, v2_errors } = evaluation.data;
  const short = (model: string) => model.replace("claimsense-decision:", "Model ");
  const config: ChartConfig = Object.fromEntries(
    models.map((m, i) => [m.model.replace(/[^a-z0-9]/gi, "_"), { label: short(m.model), color: i === models.length - 1 ? "#1B2433" : "#9AA3B2" }]),
  );
  const chartData = MEASURES.map((measure) => ({
    measure: measure.label,
    ...Object.fromEntries(models.map((m) => [m.model.replace(/[^a-z0-9]/gi, "_"), m[measure.key]])),
  }));
  return (
    <>
      <PageTitle
        title="Metrics"
        hint="Model v1 and model v2 on the same 300 synthetic v2 test claims. Line decisions are derived from the criteria, as the pipeline derives them."
      />
      <Section title="Decision model">
        {models.length === 0 ? (
          <EmptyState title="No evaluation results yet">
            Run <code>uv run python -m training.evaluate.compare_v2</code> to evaluate the models.
          </EmptyState>
        ) : (
          <>
            <div className="overflow-hidden rounded-lg border border-rules bg-paper">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Model</TableHead>
                    <TableHead className="text-right">Valid output</TableHead>
                    <TableHead className="text-right">Line accuracy</TableHead>
                    <TableHead className="text-right">Macro-F1</TableHead>
                    <TableHead className="text-right">Criterion accuracy</TableHead>
                    <TableHead className="text-right">Deny precision</TableHead>
                    <TableHead className="text-right">Median time per claim</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {models.map((row) => (
                    <TableRow key={row.model}>
                      <TableCell>
                        <span className="font-semibold">{short(row.model)}</span>
                        <div className="text-[13px] text-ink-muted">
                          Prompt {row.prompt}, {row.records} claims
                        </div>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{percent(row.valid_output)}</TableCell>
                      <TableCell className="text-right tabular-nums">{row.line_accuracy.toFixed(3)}</TableCell>
                      <TableCell className="text-right whitespace-nowrap tabular-nums">
                        {row.macro_f1.toFixed(3)}
                        <Target met={row.macro_f1 >= macro_f1_target} />
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{row.criterion_accuracy.toFixed(3)}</TableCell>
                      <TableCell className="text-right tabular-nums">{row.deny_precision.toFixed(3)}</TableCell>
                      <TableCell className="text-right tabular-nums">{(row.median_ms_per_claim / 1000).toFixed(1)} s</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            <p className="mt-3 max-w-[72ch] text-[13px] text-ink-muted">
              Target: macro-F1 of at least {macro_f1_target.toFixed(2)} on line decisions. Every recommendation
              still goes to a reviewer.
            </p>
            <div className="mt-6 rounded-lg border border-rules bg-paper p-4">
              <h3 className="mb-2 font-semibold">Model v1 and model v2 side by side</h3>
              <ChartContainer config={config} className="aspect-auto h-72 w-full">
                <BarChart data={chartData} margin={{ left: -16, right: 8 }}>
                  <CartesianGrid vertical={false} stroke="#DADDE3" />
                  <XAxis dataKey="measure" tickLine={false} axisLine={false} interval={0} tick={{ fontSize: 12, fill: "#525C6C" }} />
                  <YAxis domain={[0, 1]} tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: "#525C6C" }} />
                  <ChartTooltip content={<ChartTooltipContent />} />
                  <ChartLegend content={<ChartLegendContent />} />
                  {Object.keys(config).map((key) => (
                    <Bar key={key} dataKey={key} fill={`var(--color-${key})`} radius={[2, 2, 0, 0]} isAnimationActive={false} />
                  ))}
                </BarChart>
              </ChartContainer>
            </div>
          </>
        )}
      </Section>
      {v2_errors && (
        <Section title="Where v2 goes wrong">
          <p className="mb-3 max-w-[72ch] text-ink-muted">
            {v2_errors.wrong_lines} of {v2_errors.lines} model lines are wrong. Every recommendation goes to a
            reviewer; {v2_errors.quick_claims_with_wrong_line} of the {v2_errors.quick_claims} claims routed to
            quick review contain a wrong line.
          </p>
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="overflow-hidden rounded-lg border border-rules bg-paper">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Should be</TableHead>
                    <TableHead>Model v2 gave</TableHead>
                    <TableHead className="text-right">Lines</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {v2_errors.directions.map((row) => (
                    <TableRow key={`${row.gold}-${row.predicted}`}>
                      <TableCell>{DECISION[row.gold].label}</TableCell>
                      <TableCell>{DECISION[row.predicted].label}</TableCell>
                      <TableCell className="text-right tabular-nums">{row.lines}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            <div className="overflow-hidden rounded-lg border border-rules bg-paper">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Policy</TableHead>
                    <TableHead className="text-right">Wrong lines</TableHead>
                    <TableHead className="text-right">Lines</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {v2_errors.policies.map((row) => (
                    <TableRow key={row.policy_id}>
                      <TableCell>{row.policy_id}</TableCell>
                      <TableCell className="text-right tabular-nums">{row.wrong}</TableCell>
                      <TableCell className="text-right tabular-nums">{row.lines}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        </Section>
      )}
      <Section title="Scanned-form reading">
        {ocr ? (
          <p className="max-w-[72ch]">
            Field accuracy <span className="font-semibold tabular-nums">{percent(ocr.field_accuracy)}</span>
            <Target met={ocr.field_accuracy >= ocr_target} /> on {ocr.fields.toLocaleString("en-US")} fields of{" "}
            {ocr.claims} held-out scans (target {percent(ocr_target)}). Blank boxes read as blank:{" "}
            {percent(ocr.blank_read_as_blank)}.
          </p>
        ) : (
          <EmptyState title="No OCR results yet">
            Run <code>uv run python -m scripts.verify.ocr_accuracy</code> to measure it.
          </EmptyState>
        )}
      </Section>
    </>
  );
}
