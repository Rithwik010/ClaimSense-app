// Profile (D-MEM-2): who the member is to the plan: name, member ID, plan and coverage dates, as the
// API sends them. Nothing else of the member's record is shown.

import { useMemberProfile } from "@/api/hooks";
import { PageTitle, Panel } from "@/components/Layout";
import { ErrorNotice, Skeleton } from "@/components/States";
import { dateOnly } from "@/lib/format";

export function MemberProfile() {
  const profile = useMemberProfile();
  if (profile.isPending) return <Skeleton lines={5} />;
  if (profile.error) return <ErrorNotice error={profile.error} onRetry={() => void profile.refetch()} />;
  const p = profile.data;
  const rows: [string, string][] = [
    ["Name", p.name],
    ["Member ID", p.member_id],
    ["Plan", `${p.plan_name} (${p.plan_type})`],
    ["Coverage from", dateOnly(p.coverage_start)],
    ["Coverage until", p.coverage_end ? dateOnly(p.coverage_end) : "No end date"],
  ];
  return (
    <>
      <PageTitle title="Profile" hint="Your details as your plan has them." />
      <Panel glass className="max-w-2xl px-5 py-2">
        <dl>
          {rows.map(([term, value]) => (
            <div key={term} className="grid gap-x-4 border-b border-rules py-3 last:border-b-0 sm:grid-cols-[10rem_1fr]">
              <dt className="text-ink-muted">{term}</dt>
              <dd className="min-w-0 font-semibold break-words">{value}</dd>
            </div>
          ))}
        </dl>
      </Panel>
    </>
  );
}
