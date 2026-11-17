// The layout shared by Review claim and Claim detail (DESIGN.md): the stage strip across the top;
// left, the service lines with their criteria (and rule checks, fields, amounts, plus any extra
// tabs); right, sticky on wide screens and below the lines on small ones, three tabs (D-UI-6): the
// summary the API builds from the record (opens first), the clinical note with every evidence
// quote highlighted (selecting a criterion's quote switches to it, scrolls to the quote and pulses
// it), and the audit trail.

import { useState, type ReactNode } from "react";

import type { AuditEvent, ClaimView, FinalLineDecision } from "@/api/types";
import { AdjustmentCodes } from "@/components/AdjustmentCodes";
import { AuditTimeline } from "@/components/AuditTimeline";
import { ClaimHeader, claimLines } from "@/components/ClaimHeader";
import { ClaimSummary } from "@/components/ClaimSummary";
import { ClinicalNote, type Quote } from "@/components/ClinicalNote";
import { FieldsTable } from "@/components/Fields";
import { PlanPanel } from "@/components/PlanPanel";
import { AmountsTable, RuleChecks } from "@/components/Record";
import { quoteKey, ServiceLines } from "@/components/ServiceLines";
import { StageStrip, stages } from "@/components/StageStrip";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { evidenceChecks } from "@/lib/labels";

type Side = "summary" | "note" | "audit";

const SIDE_TABS: { value: Side; label: string }[] = [
  { value: "summary", label: "Summary" },
  { value: "note", label: "Clinical note" },
  { value: "audit", label: "Audit trail" },
];

export function ClaimWorkspace({
  view,
  events,
  fill,
  extraTabs = [],
  audit,
  lineActions,
  lineStatus,
  providerName,
}: {
  view: ClaimView;
  providerName?: string | null;
  events: AuditEvent[];
  fill: boolean;
  extraTabs?: { value: string; label: string; content: ReactNode }[];
  audit?: ReactNode; // the Audit trail tab's content; by default the timeline of `events`
  lineActions?: (line: FinalLineDecision) => ReactNode;
  lineStatus?: (line: FinalLineDecision) => ReactNode;
}) {
  const [active, setActive] = useState<{ key: string; n: number } | null>(null);
  const [side, setSide] = useState<Side>("summary");
  const record = view.record;
  const claim = view.intake?.claim ?? view.received;
  const procedures = Object.fromEntries(
    claimLines(claim).map((line) => [
      line.line_no,
      { code: line.procedure_code, name: view.names?.procedures[line.procedure_code] ?? null },
    ]),
  );
  const notes = typeof claim.clinical_notes === "string" ? claim.clinical_notes : "";
  const unquoted = new Set(
    evidenceChecks(record?.output_errors ?? []).map((c) => quoteKey(c.lineNo, c.criterionId)),
  );
  const quotes: Quote[] = (record?.slm_output?.lines ?? []).flatMap((line) =>
    line.criteria
      .filter((c) => (c.status === "MET" || c.status === "NOT_MET") && c.evidence)
      .map((c) => ({ key: quoteKey(line.line_no, c.criterion_id), text: c.evidence }))
      .filter((q) => !unquoted.has(q.key)),
  );
  const tabs = [
    {
      value: "lines",
      label: "Lines",
      content: record ? (
        <div className="space-y-3">
          <AdjustmentCodes
            title="Claim adjustment codes"
            items={(view.adjustments ?? []).filter(
              (a) => a.line_no === null || !record.line_decisions.some((l) => l.line_no === a.line_no),
            )}
          />
          <ServiceLines
          record={record}
          activeKey={active?.key ?? null}
          onQuote={(key) => {
            setSide("note");
            setActive((now) => ({ key, n: (now?.n ?? 0) + 1 }));
          }}
          actions={lineActions}
          status={lineStatus}
          adjustments={view.adjustments ?? []}
          procedures={procedures}
        />
        </div>
      ) : (
        <p className="surface rounded-lg p-4 text-ink-muted">
          Not processed yet. Process the claim to run the rules, the model and the calculator.
        </p>
      ),
    },
    ...(record
      ? [
          { value: "rules", label: "Rule checks", content: <RuleChecks record={record} /> },
          { value: "amounts", label: "Amounts", content: <AmountsTable record={record} /> },
        ]
      : []),
    { value: "plan", label: "Plan", content: <PlanPanel record={record} /> },
    {
      value: "fields",
      label: "Fields",
      content: (
        <FieldsTable claim={claim} confidences={view.field_confidences} jsonClaim={view.source_format === "JSON"} />
      ),
    },
    ...extraTabs,
  ];
  return (
    <>
      <ClaimHeader claim={claim} names={view.names} providerName={providerName ?? view.names?.provider} />
      <StageStrip list={stages(view, events)} fill={fill} />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Tabs defaultValue="lines" className="min-w-0">
          <div className="overflow-x-auto">
            <TabsList variant="line" className="mb-4 h-10 gap-4 border-b border-rules px-0">
              {tabs.map((tab) => (
                <TabsTrigger
                  key={tab.value}
                  value={tab.value}
                  className="flex-none px-0 text-[15px] text-ink-muted data-active:text-ink data-active:font-semibold"
                >
                  {tab.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </div>
          {tabs.map((tab) => (
            <TabsContent key={tab.value} value={tab.value} className="min-w-0">
              {tab.content}
            </TabsContent>
          ))}
        </Tabs>
        <aside
          aria-label="Summary, clinical note and audit trail"
          className="min-w-0 lg:sticky lg:top-20 lg:self-start"
        >
          <Tabs value={side} onValueChange={(value) => setSide(value as Side)} className="glass edge-light gap-0 rounded-lg">
            <div className="overflow-x-auto border-b border-rules px-4">
              <TabsList variant="line" aria-label="Claim side panel" className="h-11 gap-5 px-0">
                {SIDE_TABS.map((tab) => (
                  <TabsTrigger
                    key={tab.value}
                    value={tab.value}
                    className="flex-none px-0 text-[15px] text-ink-muted data-active:text-ink data-active:font-semibold"
                  >
                    {tab.label}
                  </TabsTrigger>
                ))}
              </TabsList>
            </div>
            <div className="max-h-none overflow-auto px-4 py-4 lg:max-h-[calc(100vh-12rem)]">
              <TabsContent value="summary">
                <ClaimSummary summary={view.summary} />
              </TabsContent>
              <TabsContent value="note">
                <ClinicalNote notes={notes} quotes={quotes} active={active} />
              </TabsContent>
              <TabsContent value="audit">
                {audit ?? (
                  <div data-testid="audit-trail">
                    <AuditTimeline events={events} />
                  </div>
                )}
              </TabsContent>
            </div>
          </Tabs>
        </aside>
      </div>
    </>
  );
}
