// The header's tools for every logged-in user: jump to a claim by its ID (D-UI-12) and the
// notifications bell (D-NTF-1). The bell lists what happened lately on the user's claims, asked again
// every 30 seconds; which ones are new is kept in this browser only (the newest event opened), so
// nothing about reading them is stored on the server.

import { Bell, Search } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router";

import { ApiError, request } from "@/api/client";
import { useNotifications } from "@/api/hooks";
import type { Notification, Role } from "@/api/types";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { useUser } from "@/lib/auth";
import { age } from "@/lib/format";
import { APPEAL_OUTCOME, memberOutcome, OUTCOME } from "@/lib/labels";

/** Where a role opens a claim, and the API path that says whether it may. */
export function claimPaths(role: Role, claimId: string): { page: string; api: string } {
  const id = encodeURIComponent(claimId);
  if (role === "member") return { page: `/member/claims/${id}`, api: `/v1/member/claims/${id}` };
  if (role === "provider") return { page: `/my-claims/${id}`, api: `/v1/claims/${id}` };
  return { page: `/claims/${id}`, api: `/v1/claims/${id}` };
}

/** Jump to a claim by its ID: the claim's page when it is there for this user, else a short note. */
export function ClaimJump() {
  const { role } = useUser();
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <form
      role="search"
      className="relative hidden min-w-0 md:block"
      onSubmit={async (event) => {
        event.preventDefault();
        const claimId = text.trim().toUpperCase();
        if (!claimId) return;
        setBusy(true);
        setNote(null);
        const paths = claimPaths(role, claimId);
        try {
          await request(paths.api);
          setText("");
          navigate(paths.page);
        } catch (error) {
          setNote(error instanceof ApiError && error.status === 404 ? `No claim ${claimId} for you` : "Could not look it up");
        } finally {
          setBusy(false);
        }
      }}
    >
      <label htmlFor="jump-claim" className="sr-only">
        Go to a claim by its ID
      </label>
      <Search aria-hidden className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-ink-muted" />
      <Input
        id="jump-claim"
        value={text}
        disabled={busy}
        placeholder="Go to claim ID"
        aria-describedby={note ? "jump-claim-note" : undefined}
        className="h-9 w-44 bg-paper pl-8 text-[14px] lg:w-56"
        onChange={(event) => {
          setText(event.target.value);
          setNote(null);
        }}
      />
      {note && (
        <p
          id="jump-claim-note"
          role="status"
          className="absolute top-full left-0 mt-1 rounded-md border border-rules bg-white px-2 py-1 text-[13px] whitespace-nowrap shadow-sm"
        >
          {note}
        </p>
      )}
    </form>
  );
}

const SEEN_KEY = "claimsense.notifications.seen";

function readSeen(username: string): number {
  try {
    return Number(window.localStorage.getItem(`${SEEN_KEY}.${username}`) ?? 0) || 0;
  } catch {
    return 0;
  }
}

function writeSeen(username: string, id: number): void {
  try {
    window.localStorage.setItem(`${SEEN_KEY}.${username}`, String(id));
  } catch {
    // A private window: every notification shows as new each visit.
  }
}

/** A notification in plain words for the user's role. */
export function notificationText(n: Notification, role: Role): string {
  const outcome =
    n.outcome && role === "member"
      ? memberOutcome(n.outcome).label.toLowerCase()
      : n.outcome && n.outcome !== "DUPLICATE"
        ? OUTCOME[n.outcome].label.toLowerCase()
        : "decided";
  switch (n.event_type) {
    case "FINALIZED":
    case "AUTO_OUTCOME":
      return `Claim ${n.claim_id} is final: ${outcome}`;
    case "APPEAL_DECIDED":
      return `The appeal of claim ${n.claim_id} is decided: ${(APPEAL_OUTCOME[n.appeal_outcome ?? ""] ?? "decided").toLowerCase()}`;
    case "SLM_RECOMMENDED":
      return `Claim ${n.claim_id} is ready for review`;
    case "OUTPUT_INVALID":
      return role === "admin"
        ? `Claim ${n.claim_id}: the model's answer could not be used`
        : `Claim ${n.claim_id} is ready for a full review (the model's answer could not be used)`;
    case "APPEAL_FILED":
      return `Claim ${n.claim_id} was appealed: another reviewer decides it again`;
    case "CALCULATION_FAILED":
      return `Claim ${n.claim_id}: the amounts could not be calculated`;
    default:
      return `Claim ${n.claim_id} changed`;
  }
}

function target(n: Notification, role: Role): string {
  if (role === "reviewer" && (n.event_type === "SLM_RECOMMENDED" || n.event_type === "OUTPUT_INVALID" || n.event_type === "APPEAL_FILED")) {
    return `/review/${encodeURIComponent(n.claim_id)}`;
  }
  return claimPaths(role, n.claim_id).page;
}

export function NotificationBell() {
  const user = useUser();
  const notifications = useNotifications();
  const [seen, setSeen] = useState(() => readSeen(user.username));
  const items = notifications.data?.items ?? [];
  const fresh = items.filter((n) => n.id > seen).length;
  return (
    <DropdownMenu
      onOpenChange={(open) => {
        // New ones stay marked while the list is open, and are read once it closes.
        const latest = notifications.data?.latest_id ?? 0;
        if (open && latest > seen) writeSeen(user.username, latest);
        if (!open) setSeen(readSeen(user.username));
      }}
    >
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="relative rounded-full"
          aria-label={fresh ? `Notifications: ${fresh} new` : "Notifications"}
        >
          <Bell aria-hidden className="size-5" />
          {fresh > 0 && (
            <span className="absolute -top-0.5 -right-0.5 grid min-w-5 place-items-center rounded-full bg-primary px-1 text-[11px] leading-5 font-semibold text-white tabular-nums">
              {fresh > 9 ? "9+" : fresh}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="glass-strong w-80 rounded-lg p-1 ring-0">
        <DropdownMenuLabel className="px-2 py-1.5 text-[15px] font-semibold">Notifications</DropdownMenuLabel>
        <DropdownMenuSeparator className="bg-rules" />
        {notifications.isPending ? (
          <p className="px-2 py-3 text-[14px] text-ink-muted">Looking for news…</p>
        ) : notifications.error ? (
          <p className="px-2 py-3 text-[14px] text-ink-muted">Notifications are not available right now.</p>
        ) : items.length === 0 ? (
          <p className="px-2 py-3 text-[14px] text-ink-muted">Nothing yet. Decisions on your claims show here.</p>
        ) : (
          <div className="max-h-96 overflow-y-auto">
            {items.map((n) => (
              <DropdownMenuItem key={n.id} asChild className="items-start px-2 py-2">
                <Link to={target(n, user.role)}>
                  <span
                    aria-hidden
                    className={`mt-1.5 size-2 shrink-0 rounded-full ${n.id > seen ? "bg-primary" : "bg-transparent"}`}
                  />
                  <span className="min-w-0">
                    <span className="block text-[14px] leading-5 text-ink">
                      {n.id > seen && <span className="sr-only">New: </span>}
                      {notificationText(n, user.role)}
                    </span>
                    <span className="block text-[12px] text-ink-muted">{age(n.created_at)} ago</span>
                  </span>
                </Link>
              </DropdownMenuItem>
            ))}
          </div>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
