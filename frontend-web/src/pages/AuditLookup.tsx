// Audit lookup (admin, D-AUD-1): find audit events by claim ID, by who acted, by event and by date.
// A claim ID alone shows that claim's trail as a timeline, oldest step first; any other search lists
// the matching events across claims, newest first (up to 200), each with what it did. Read-only;
// the trail itself is insert-only on the server (§8.9). The search is kept in the URL.

import { Search } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router";

import { useAuditSearch, type AuditQuery } from "@/api/hooks";
import { AuditTimeline, corrections, details, EVENTS } from "@/components/AuditTimeline";
import { PageTitle } from "@/components/Layout";
import { CsvButton } from "@/components/ListTools";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { dateTimeSeconds } from "@/lib/format";

const KEYS = ["claim_id", "actor", "event_type", "since", "until"] as const;
const ANY = "any";

function fromParams(params: URLSearchParams): AuditQuery | null {
  const query: AuditQuery = {};
  for (const key of KEYS) {
    const value = params.get(key)?.trim();
    if (value) query[key] = value;
  }
  return Object.keys(query).length ? query : null;
}

export function AuditLookup() {
  const [params, setParams] = useSearchParams();
  const searched = fromParams(params);
  const [form, setForm] = useState<AuditQuery>(() => searched ?? {});
  const search = useAuditSearch(searched);
  const claimOnly = searched !== null && Object.keys(searched).length === 1 && Boolean(searched.claim_id);
  const events = search.data?.events ?? [];
  const set = (key: keyof AuditQuery, value: string) => setForm((now) => ({ ...now, [key]: value }));
  const eventTypes = search.data?.event_types ?? Object.keys(EVENTS);
  return (
    <>
      <PageTitle
        title="Audit lookup"
        hint="Every step of every claim: when it happened, who did it, and the versions it ran with. Search by claim, by who acted, by event or by date."
      />
      <form
        className="surface mb-6 grid gap-3 rounded-lg p-4 sm:grid-cols-2 lg:grid-cols-[repeat(5,minmax(0,1fr))_auto] lg:items-end"
        onSubmit={(event) => {
          event.preventDefault();
          const next = new URLSearchParams();
          for (const key of KEYS) {
            const value = form[key]?.trim();
            if (value && value !== ANY) next.set(key, value);
          }
          setParams(next, { replace: false });
        }}
      >
        <label className="grid min-w-0 gap-1.5 text-[13px] font-semibold" htmlFor="audit-claim">
          Claim ID
          <span className="relative">
            <Search aria-hidden className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-muted" />
            <Input
              id="audit-claim"
              value={form.claim_id ?? ""}
              placeholder="CLM-DEMO-03"
              className="h-10 bg-paper pl-9 text-[15px] font-normal"
              onChange={(event) => set("claim_id", event.target.value)}
            />
          </span>
        </label>
        <label className="grid min-w-0 gap-1.5 text-[13px] font-semibold" htmlFor="audit-actor">
          Who acted
          <Input
            id="audit-actor"
            value={form.actor ?? ""}
            placeholder="A username, or system"
            className="h-10 bg-paper text-[15px] font-normal"
            onChange={(event) => set("actor", event.target.value)}
          />
        </label>
        <label className="grid min-w-0 gap-1.5 text-[13px] font-semibold" htmlFor="audit-event">
          Event
          <Select value={form.event_type || ANY} onValueChange={(value) => set("event_type", value === ANY ? "" : value)}>
            <SelectTrigger id="audit-event" className="h-10 w-full bg-paper text-[15px] font-normal data-[size=default]:h-10">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any event</SelectItem>
              {eventTypes.map((type) => (
                <SelectItem key={type} value={type}>
                  {EVENTS[type] ?? type}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </label>
        <label className="grid min-w-0 gap-1.5 text-[13px] font-semibold" htmlFor="audit-since">
          From
          <Input
            id="audit-since"
            type="date"
            value={form.since ?? ""}
            className="h-10 bg-paper text-[15px] font-normal"
            onChange={(event) => set("since", event.target.value)}
          />
        </label>
        <label className="grid min-w-0 gap-1.5 text-[13px] font-semibold" htmlFor="audit-until">
          To
          <Input
            id="audit-until"
            type="date"
            value={form.until ?? ""}
            className="h-10 bg-paper text-[15px] font-normal"
            onChange={(event) => set("until", event.target.value)}
          />
        </label>
        <Button type="submit" size="lg" disabled={!KEYS.some((key) => (form[key] ?? "").trim() && form[key] !== ANY)}>
          Show audit trail
        </Button>
      </form>
      {searched === null ? (
        <EmptyState title="Search the audit trail">
          Enter a claim ID to see its trail, or search by who acted, by event or by date across every claim.
        </EmptyState>
      ) : search.isPending ? (
        <Skeleton lines={5} />
      ) : search.error ? (
        <ErrorNotice error={search.error} onRetry={() => void search.refetch()} />
      ) : events.length === 0 ? (
        <EmptyState title={claimOnly ? `No claim ${searched.claim_id} on file` : "No events match"}>
          {claimOnly ? "Check the claim ID; claim IDs look like CLM-DEMO-01." : "Change the search and try again."}
        </EmptyState>
      ) : claimOnly ? (
        <>
          <p className="mb-3 text-ink-muted">
            {events.length} steps for claim{" "}
            <Link className="font-semibold text-link underline underline-offset-4" to={`/claims/${encodeURIComponent(searched.claim_id ?? "")}`}>
              {searched.claim_id}
            </Link>
            .
          </p>
          <AuditTimeline events={[...events].reverse()} />
        </>
      ) : (
        <>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <p className="text-ink-muted">
              {events.length === search.data?.limit
                ? `The latest ${events.length} events that match. Narrow the search to see older ones.`
                : `${events.length} event${events.length === 1 ? "" : "s"}, newest first.`}
            </p>
            <CsvButton
              rows={events}
              fileName="audit-events.csv"
              columns={[
                { header: "Time", value: (e) => e.created_at },
                { header: "Claim ID", value: (e) => e.claim_id },
                { header: "Event", value: (e) => EVENTS[e.event_type] ?? e.event_type },
                { header: "Actor", value: (e) => e.actor },
                { header: "Details", value: (e) => [...corrections(e), ...details(e)].join("; ") },
                { header: "Request ID", value: (e) => e.request_id ?? "" },
              ]}
            />
          </div>
          <div className="surface overflow-x-auto rounded-lg">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Claim</TableHead>
                  <TableHead>Event</TableHead>
                  <TableHead>Who</TableHead>
                  <TableHead>Details</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {events.map((event) => (
                  <TableRow key={event.id}>
                    <TableCell className="text-[13px] whitespace-nowrap tabular-nums">{dateTimeSeconds(event.created_at)}</TableCell>
                    <TableCell>
                      <Link
                        className="font-semibold whitespace-nowrap text-link underline-offset-4 hover:underline"
                        to={`/claims/${encodeURIComponent(event.claim_id)}`}
                      >
                        {event.claim_id}
                      </Link>
                    </TableCell>
                    <TableCell className="min-w-44">{EVENTS[event.event_type] ?? event.event_type}</TableCell>
                    <TableCell className="whitespace-nowrap">{event.actor}</TableCell>
                    <TableCell className="min-w-64 text-[13px] break-words">
                      {[...corrections(event), ...details(event)].join("; ") || <span className="text-ink-muted">—</span>}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      )}
    </>
  );
}
