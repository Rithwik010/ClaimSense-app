import { useEvaluation } from "../api/hooks";
import { PageTitle, Section } from "../components/Layout";
import { EmptyState, ErrorNotice, Skeleton } from "../components/States";
import { table, td, th } from "../components/ui";
import { percent } from "../lib/format";
import { DECISION } from "../lib/labels";

function Target({ met }: { met: boolean }) {
  return (
    <span className={`ml-2 text-xs font-medium ${met ? "text-green-800" : "text-red-800"}`}>
      {met ? "target met" : "below target"}
    </span>
  );
}

export function Metrics() {
  const evaluation = useEvaluation();
  if (evaluation.isPending) return <Skeleton lines={6} />;
  if (evaluation.error) return <ErrorNotice error={evaluation.error} onRetry={() => void evaluation.refetch()} />;
  const { models, macro_f1_target, ocr, ocr_target, v2_errors } = evaluation.data;
  return (
    <>
      <PageTitle
        title="Metrics"
        hint="Model v1 and model v2 on the same 300 synthetic v2 test claims, with line decisions derived from the criteria."
      />
      <Section title="Decision model">
        {models.length === 0 ? (
          <EmptyState title="No evaluation results yet">
            Run <code>uv run python -m training.evaluate.compare_v2</code>.
          </EmptyState>
        ) : (
          <div className="overflow-auto rounded-md border border-gray-200">
            <table className={table}>
              <thead>
                <tr>
                  <th scope="col" className={th}>Model</th>
                  <th scope="col" className={`${th} text-right`}>Valid output</th>
                  <th scope="col" className={`${th} text-right`}>Line accuracy</th>
                  <th scope="col" className={`${th} text-right`}>Macro-F1</th>
                  <th scope="col" className={`${th} text-right`}>Criterion accuracy</th>
                  <th scope="col" className={`${th} text-right`}>DENY precision</th>
                  <th scope="col" className={`${th} text-right`}>Median time per claim</th>
                </tr>
              </thead>
              <tbody>
                {models.map((row) => (
                  <tr key={row.model}>
                    <td className={td}>
                      <span className="font-medium">{row.model}</span>
                      <div className="text-gray-600">prompt {row.prompt}, {row.records} claims</div>
                    </td>
                    <td className={`${td} text-right tabular-nums`}>{percent(row.valid_output)}</td>
                    <td className={`${td} text-right tabular-nums`}>{row.line_accuracy.toFixed(3)}</td>
                    <td className={`${td} text-right tabular-nums`}>
                      {row.macro_f1.toFixed(3)}
                      <Target met={row.macro_f1 >= macro_f1_target} />
                    </td>
                    <td className={`${td} text-right tabular-nums`}>{row.criterion_accuracy.toFixed(3)}</td>
                    <td className={`${td} text-right tabular-nums`}>{row.deny_precision.toFixed(3)}</td>
                    <td className={`${td} text-right tabular-nums`}>{(row.median_ms_per_claim / 1000).toFixed(1)} s</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="mt-3 text-sm text-gray-600">
          Target: macro-F1 of at least {macro_f1_target.toFixed(2)} on line decisions. Every
          recommendation still goes to a reviewer.
        </p>
      </Section>
      {v2_errors && (
        <Section title="Where v2 goes wrong">
          <p className="mb-3 text-gray-700">
            {v2_errors.wrong_lines} of {v2_errors.lines} model lines are wrong. Every
            recommendation goes to a reviewer; {v2_errors.quick_claims_with_wrong_line} of the{" "}
            {v2_errors.quick_claims} claims routed to quick review hold a wrong line.
          </p>
          <div className="grid gap-6 md:grid-cols-2">
            <div className="overflow-auto rounded-md border border-gray-200">
              <table className={table}>
                <thead>
                  <tr>
                    <th scope="col" className={th}>Should be</th>
                    <th scope="col" className={th}>Model v2 gave</th>
                    <th scope="col" className={`${th} text-right`}>Lines</th>
                  </tr>
                </thead>
                <tbody>
                  {v2_errors.directions.map((row) => (
                    <tr key={`${row.gold}-${row.predicted}`}>
                      <td className={td}>{DECISION[row.gold].label}</td>
                      <td className={td}>{DECISION[row.predicted].label}</td>
                      <td className={`${td} text-right tabular-nums`}>{row.lines}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="overflow-auto rounded-md border border-gray-200">
              <table className={table}>
                <thead>
                  <tr>
                    <th scope="col" className={th}>Policy</th>
                    <th scope="col" className={`${th} text-right`}>Wrong lines</th>
                    <th scope="col" className={`${th} text-right`}>Lines</th>
                  </tr>
                </thead>
                <tbody>
                  {v2_errors.policies.map((row) => (
                    <tr key={row.policy_id}>
                      <td className={td}>{row.policy_id}</td>
                      <td className={`${td} text-right tabular-nums`}>{row.wrong}</td>
                      <td className={`${td} text-right tabular-nums`}>{row.lines}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </Section>
      )}
      <Section title="Scanned-form reading (OCR)">
        {ocr ? (
          <p>
            Field accuracy <span className="font-medium tabular-nums">{percent(ocr.field_accuracy)}</span>
            <Target met={ocr.field_accuracy >= ocr_target} /> on {ocr.fields.toLocaleString("en-US")} fields
            of {ocr.claims} held-out scans (target {percent(ocr_target)}); blank boxes read as blank{" "}
            {percent(ocr.blank_read_as_blank)}.
          </p>
        ) : (
          <EmptyState title="No OCR results yet">
            Run <code>uv run python -m scripts.verify.ocr_accuracy</code>.
          </EmptyState>
        )}
      </Section>
    </>
  );
}
