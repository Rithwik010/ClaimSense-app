// The search box and status filter every claims list uses (D-UI-6), kept in the URL (?q= and
// ?status=) so a refresh or the back button keeps them, with the number of claims shown and an
// empty state that clears them. The provider's My claims searches claim IDs; reviewers and admins
// search claim ID, member ID, provider name or NPI (src/lib/filters.ts).

import { Search } from "lucide-react";
import { useId } from "react";
import { useSearchParams } from "react-router";

import type { Outcome } from "@/api/types";
import { EmptyState } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ALL, count, statusParam, type StatusFilter } from "@/lib/filters";
import type { Label } from "@/lib/labels";

export interface Filters {
  query: string;
  status: StatusFilter;
  active: boolean;
  setQuery: (value: string) => void;
  setStatus: (value: string) => void;
  clear: () => void;
}

/** The list's search and status from the URL; `options` null: a search with no status filter. */
export function useClaimFilters(options: readonly Outcome[] | null): Filters {
  const [params, setParams] = useSearchParams();
  const query = params.get("q") ?? "";
  const status = options ? statusParam(params.get("status"), options) : ALL;
  const change = (edit: (next: URLSearchParams) => void) =>
    setParams(
      (now) => {
        const next = new URLSearchParams(now);
        edit(next);
        return next;
      },
      { replace: true },
    );
  const set = (key: string, value: string) =>
    change((next) => (value && value !== ALL ? next.set(key, value) : next.delete(key)));
  return {
    query,
    status,
    active: query.trim() !== "" || status !== ALL,
    setQuery: (value) => set("q", value),
    setStatus: (value) => set("status", value),
    clear: () =>
      change((next) => {
        next.delete("q");
        next.delete("status");
      }),
  };
}

export function ClaimFilters({
  filters,
  searchLabel,
  placeholder,
  options,
  label,
  shown,
}: {
  filters: Filters;
  searchLabel: string;
  placeholder: string;
  options: readonly Outcome[] | null;
  label: (outcome: Outcome) => Label;
  shown: number;
}) {
  const searchId = useId();
  const statusId = useId();
  return (
    <div className="mb-4 grid gap-3 sm:flex sm:flex-wrap sm:items-end">
      <label className="grid min-w-0 gap-1.5 text-[13px] font-semibold sm:flex-1 sm:basis-64" htmlFor={searchId}>
        {searchLabel}
        <span className="relative">
          <Search aria-hidden className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-muted" />
          <Input
            id={searchId}
            value={filters.query}
            placeholder={placeholder}
            className="h-10 bg-paper pl-9 text-[15px] font-normal"
            onChange={(event) => filters.setQuery(event.target.value)}
          />
        </span>
      </label>
      {options && (
        <label className="grid min-w-0 gap-1.5 text-[13px] font-semibold sm:w-56" htmlFor={statusId}>
          Status
          <Select value={filters.status} onValueChange={filters.setStatus}>
            <SelectTrigger
              id={statusId}
              className="h-10 w-full bg-paper text-[15px] font-normal data-[size=default]:h-10"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All</SelectItem>
              {options.map((outcome) => (
                <SelectItem key={outcome} value={outcome}>
                  {label(outcome).label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </label>
      )}
      <p className="text-[13px] whitespace-nowrap text-ink-muted tabular-nums sm:pb-2.5" aria-live="polite">
        {count(shown)}
      </p>
    </div>
  );
}

/** What a list shows when nothing matches its search and filter. */
export function NoMatch({ onClear }: { onClear: () => void }) {
  return (
    <EmptyState title="No claims match">
      <p>Change the search or the status, or clear them.</p>
      <Button variant="outline" className="mt-4" onClick={onClear}>
        Clear filters
      </Button>
    </EmptyState>
  );
}
