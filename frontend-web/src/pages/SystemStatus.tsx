// System status (admin): what /health reports (the database, Qdrant, Ollama with the demo model)
// and the versions the decision records name, beside the ones the API is set to use.

import { CircleCheck, CircleX } from "lucide-react";

import { useHealth, useSystemVersions } from "@/api/hooks";
import { PageTitle, Section } from "@/components/Layout";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/States";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { dateTime } from "@/lib/format";

const SERVICES = [
  ["database", "Database (Postgres)"],
  ["qdrant", "Coverage policies (Qdrant)"],
  ["ollama", "Decision model (Ollama)"],
] as const;

const CONFIGURED: Record<string, string> = {
  model: "Model",
  prompt: "Prompt",
  policy_set: "Policy set",
  rules: "Rules",
  calculator: "Calculator",
};

export function SystemStatus() {
  const health = useHealth();
  const versions = useSystemVersions();
  return (
    <>
      <PageTitle title="System status" hint="The services the API reaches, and the versions behind every decision." />
      <Section title="Services">
        {health.isPending ? (
          <Skeleton lines={3} />
        ) : health.error ? (
          <ErrorNotice error={health.error} onRetry={() => void health.refetch()} />
        ) : (
          <ul className="divide-y divide-rules rounded-lg border border-rules bg-paper">
            {SERVICES.map(([key, label]) => {
              const service = health.data[key];
              return (
                <li key={key} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3">
                  <span
                    className={`inline-flex h-6 items-center gap-1.5 rounded-md border px-2 text-[13px] font-semibold ${
                      service.ok ? "border-approve/25 bg-approve-tint text-approve" : "border-deny/25 bg-deny-tint text-deny"
                    }`}
                  >
                    {service.ok ? <CircleCheck aria-hidden className="size-3.5" /> : <CircleX aria-hidden className="size-3.5" />}
                    {service.ok ? "Reachable" : "Not reachable"}
                  </span>
                  <span className="font-semibold">{label}</span>
                  <span className="text-[13px] text-ink-muted">{service.detail}</span>
                </li>
              );
            })}
          </ul>
        )}
      </Section>
      <Section title="Versions">
        {versions.isPending ? (
          <Skeleton lines={4} />
        ) : versions.error ? (
          <ErrorNotice error={versions.error} onRetry={() => void versions.refetch()} />
        ) : (
          <div className="space-y-6">
            <dl className="grid gap-x-6 rounded-lg border border-rules bg-paper px-4 py-3 sm:grid-cols-2 lg:grid-cols-5">
              {Object.entries(versions.data.configured).map(([key, value]) => (
                <div key={key} className="py-1.5">
                  <dt className="text-[13px] text-ink-muted">{CONFIGURED[key] ?? key} the API uses</dt>
                  <dd className="font-semibold break-words">{value}</dd>
                </div>
              ))}
            </dl>
            {versions.data.in_records.length === 0 ? (
              <EmptyState title="No decision records yet">Process a claim and its versions appear here.</EmptyState>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-rules bg-paper">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Rules</TableHead>
                      <TableHead>Model</TableHead>
                      <TableHead>Prompt</TableHead>
                      <TableHead>Policies</TableHead>
                      <TableHead className="text-right">Records</TableHead>
                      <TableHead className="text-right">Latest</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {versions.data.in_records.map((v) => (
                      <TableRow key={`${v.rules_version}-${v.model_name}-${v.prompt_version}-${v.policy_versions.join()}`}>
                        <TableCell className="tabular-nums">{v.rules_version}</TableCell>
                        <TableCell>{v.model_name ?? "Not used (decided by the rules)"}</TableCell>
                        <TableCell>{v.prompt_version ?? "—"}</TableCell>
                        <TableCell className="text-[13px]">{v.policy_versions.length ? v.policy_versions.join(", ") : "—"}</TableCell>
                        <TableCell className="text-right tabular-nums">{v.records}</TableCell>
                        <TableCell className="text-right text-[13px] whitespace-nowrap text-ink-muted">{dateTime(v.latest)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                <p className="border-t border-rules px-4 py-2 text-[13px] text-ink-muted">
                  One row per set of versions found in the decision records, the most recent first.
                </p>
              </div>
            )}
          </div>
        )}
      </Section>
    </>
  );
}
