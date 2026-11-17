// My plan (members, P3.2): the plan's summary of benefits and coverage, generated from the plan's
// terms (every figure in it is checked against the plan). The API reads it into headings,
// paragraphs, lists and tables; the page shows them, with **bold** as bold. Printable.

import { Printer } from "lucide-react";
import { Fragment } from "react";

import { usePlanSummary } from "@/api/hooks";
import type { PlanSummary } from "@/api/types";
import { PageTitle, Panel } from "@/components/Layout";
import { ErrorNotice, Skeleton } from "@/components/States";
import { Button } from "@/components/ui/button";

/** Text with **bold** spans as bold; nothing else is interpreted. */
export function Inline({ text }: { text: string }) {
  const parts = text.split("**");
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? <strong key={i}>{part}</strong> : <Fragment key={i}>{part}</Fragment>,
      )}
    </>
  );
}

type Block = PlanSummary["sections"][number]["blocks"][number];

function BlockView({ block }: { block: Block }) {
  if (block.kind === "list") {
    return (
      <ul className="mt-2 list-disc space-y-1.5 pl-5 marker:text-ink-muted">
        {block.items.map((item) => (
          <li key={item}>
            <Inline text={item} />
          </li>
        ))}
      </ul>
    );
  }
  if (block.kind === "table") {
    return (
      <div className="mt-3 overflow-x-auto rounded-lg border border-rules">
        <table className="w-full min-w-[640px] text-left text-[14px]">
          <thead className="bg-subtle">
            <tr>
              {block.header.map((cell) => (
                <th key={cell} className="px-3 py-2 font-semibold">
                  {cell}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {block.rows.map((row) => (
              <tr key={row.join("|")} className="border-t border-rules align-top">
                {row.map((cell, i) => (
                  <td key={`${i}-${cell}`} className={`px-3 py-2 ${i === 0 ? "font-semibold" : ""}`}>
                    <Inline text={cell} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  return (
    <p className="mt-2 max-w-[80ch]">
      <Inline text={block.text ?? ""} />
    </p>
  );
}

export function MemberPlan() {
  const summary = usePlanSummary();
  if (summary.isPending) return <Skeleton lines={10} />;
  if (summary.error) return <ErrorNotice error={summary.error} onRetry={() => void summary.refetch()} />;
  const data = summary.data;
  return (
    <>
      <PageTitle
        title="My plan"
        hint={data.title}
        actions={
          <Button variant="outline" className="print:hidden" onClick={() => window.print()}>
            <Printer aria-hidden /> Print
          </Button>
        }
      />
      <div className="space-y-6">
        {data.sections.map((section, i) => (
          <Panel key={section.heading ?? `intro-${i}`} className="p-5">
            {section.heading && <h2 className="text-[21px] leading-[28px] font-bold">{section.heading}</h2>}
            {section.blocks.map((block, j) => (
              <BlockView key={j} block={block} />
            ))}
          </Panel>
        ))}
      </div>
    </>
  );
}
