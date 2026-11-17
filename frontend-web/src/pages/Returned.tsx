// Returned and auto-denied (read-only; the URL stays /rule-outcomes): claims the automatic checks
// decided on their own (REJECTED, DENIED_BY_RULE, PENDED_BY_RULE), with the Reason column, each failed
// rule's detail and the standard CARC/RARC codes (D-CARC-2). They never reach the review queue
// (§8.8). Search and a status filter of Rejected, Denied and Pended, kept in the URL (D-UI-6). One
// card a claim, so the codes never need sideways scrolling (fix 5).

import { Link } from "react-router";

import { useClaims } from "@/api/hooks";
import type { ClaimStatus } from "@/api/types";
import { ClaimFilters, NoMatch, useClaimFilters } from "@/components/ClaimFilters";
import { OutcomeChip, PlainBadge } from "@/components/Chip";
import { PageTitle } from "@/components/Layout";
import { ReasonCell } from "@/components/ReasonCell";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/States";
import { matches } from "@/lib/filters";
import { OUTCOME, reason, RETURNED_FILTERS } from "@/lib/labels";

const RULE_STATUSES: ClaimStatus[] = ["REJECTED", "DENIED_BY_RULE", "PENDED_BY_RULE"];
export const RETURNED_TITLE = "Returned and auto-denied";

export function Returned() {
  const claims = useClaims(RULE_STATUSES);
  const filters = useClaimFilters(RETURNED_FILTERS);
  const shown = (claims.data ?? []).filter((c) => matches(c, filters.query, filters.status, "all"));
  return (
    <>
      <PageTitle
        title={RETURNED_TITLE}
        hint="Claims the automatic checks returned, denied or put on hold, without a reviewer."
      />
      {claims.isPending ? (
        <Skeleton lines={5} />
      ) : claims.error ? (
        <ErrorNotice error={claims.error} onRetry={() => void claims.refetch()} />
      ) : claims.data.length === 0 ? (
        <EmptyState title="Nothing returned or auto-denied yet">
          A claim that fails an automatic check (for example a missing field or a lapsed member) appears here after
          processing.
        </EmptyState>
      ) : (
        <>
          <ClaimFilters
            filters={filters}
            searchLabel="Search claims"
            placeholder="Claim ID, member ID, provider name or NPI"
            options={RETURNED_FILTERS}
            label={(outcome) => OUTCOME[outcome]}
            shown={shown.length}
          />
          {shown.length === 0 ? (
            <NoMatch onClear={filters.clear} />
          ) : (
            // One card a claim, its reasons and codes side by side from 1024 px: nothing to scroll
            // sideways, whatever the width (fix 5).
            <ul aria-label="Claims decided by the checks" className="grid gap-3">
              {shown.map((claim) => (
                <li key={claim.claim_id} className="surface rounded-lg p-4 md:p-5">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                    <Link
                      className="font-semibold whitespace-nowrap text-link underline-offset-4 transition-colors hover:text-primary-hover hover:underline"
                      to={`/claims/${encodeURIComponent(claim.claim_id)}`}
                    >
                      {claim.claim_id}
                    </Link>
                    <OutcomeChip outcome={claim.outcome} />
                    <span className="min-w-0 flex-1 basis-64 text-[14px]">
                      <ReasonCell reasons={claim.reasons} />
                    </span>
                  </div>
                  <div className="mt-3 grid gap-4 border-t border-rules pt-3 lg:grid-cols-2">
                    <section aria-label="Why">
                      <h3 className="text-[13px] font-semibold text-ink-muted">Why</h3>
                      <ul className="mt-1 space-y-2">
                        {claim.failed_rules.map((rule, i) => (
                          <li key={`${rule.rule_id}-${i}`} className="break-words">
                            <span className="font-semibold">
                              Rule {rule.rule_id}
                              {rule.line_no ? `, line ${rule.line_no}` : ""}
                            </span>
                            : {reason(rule.reason_code)}
                            <div className="text-[13px] text-ink-muted">{rule.detail}</div>
                          </li>
                        ))}
                      </ul>
                    </section>
                    <section aria-label="Codes">
                      <h3 className="text-[13px] font-semibold text-ink-muted">Codes</h3>
                      {claim.adjustments.length ? (
                        <ul className="mt-1 space-y-2">
                          {claim.adjustments.flatMap((a) =>
                            a.codes.map((c) => (
                              <li key={`${a.line_no ?? "claim"}-${c.kind}-${c.code}`} className="grid grid-cols-[auto_1fr] gap-x-2">
                                <PlainBadge>
                                  {c.kind} {c.code}
                                </PlainBadge>
                                <span className="text-[13px] leading-5 break-words text-ink-muted">
                                  {c.description ?? "Description not loaded"}
                                </span>
                              </li>
                            )),
                          )}
                        </ul>
                      ) : (
                        <p className="mt-1 text-ink-muted">None</p>
                      )}
                    </section>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </>
  );
}
