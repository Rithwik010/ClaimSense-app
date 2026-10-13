// What the claim lists search and filter on (D-UI-6): a provider searches their claim IDs; a
// reviewer or admin searches claim ID, member ID, provider name or NPI. Case-insensitive, partial.
// The status filter matches the outcome the API names for each claim.

import type { Outcome } from "@/api/types";

export const ALL = "all";
export type StatusFilter = Outcome | typeof ALL;

export interface Searchable {
  claim_id: string;
  member_id?: string | null;
  provider_name?: string | null;
  provider_npi?: string | null;
  outcome?: Outcome;
}

/** The fields a search looks in: the claim ID only, or every field a reviewer searches. */
export function searchIn(item: Searchable, fields: "claim" | "all"): string[] {
  const found = [item.claim_id];
  if (fields === "all") found.push(item.member_id ?? "", item.provider_name ?? "", item.provider_npi ?? "");
  return found;
}

export function matches(item: Searchable, query: string, status: StatusFilter, fields: "claim" | "all"): boolean {
  const wanted = query.trim().toLowerCase();
  const found = !wanted || searchIn(item, fields).some((value) => value.toLowerCase().includes(wanted));
  return found && (status === ALL || item.outcome === status);
}

/** A status from the URL, or "all" when it is not one of the page's options. */
export function statusParam(value: string | null, options: readonly Outcome[]): StatusFilter {
  return value && (options as readonly string[]).includes(value) ? (value as Outcome) : ALL;
}

export function count(n: number, noun = "claim"): string {
  return `${n} ${noun}${n === 1 ? "" : "s"}`;
}
