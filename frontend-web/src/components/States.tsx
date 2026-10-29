// Loading skeletons, empty states that say what to do next, and API errors in plain words.

import { CircleAlert, WifiOff } from "lucide-react";
import type { ReactNode } from "react";

import { ApiError } from "@/api/client";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton as Bar } from "@/components/ui/skeleton";

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div role="status" aria-label="Loading" className="space-y-3">
      {Array.from({ length: lines }, (_, i) => (
        <Bar key={i} className="h-4 bg-rules/60" style={{ width: `${90 - i * 12}%` }} />
      ))}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-control bg-subtle px-6 py-12 text-center">
      <p className="font-semibold">{title}</p>
      {children && <div className="mx-auto mt-2 max-w-[60ch] text-ink-muted">{children}</div>}
    </div>
  );
}

export function ErrorNotice({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  const unreachable = error instanceof ApiError && error.status === 0;
  return (
    <Alert className="border-deny/30 bg-deny-tint text-deny">
      {unreachable ? <WifiOff aria-hidden /> : <CircleAlert aria-hidden />}
      <AlertTitle>{unreachable ? "The server can't be reached" : "The request did not go through"}</AlertTitle>
      <AlertDescription className="text-ink">
        <p>{message}</p>
        {onRetry && (
          <Button variant="outline" className="mt-3" onClick={onRetry}>
            Try again
          </Button>
        )}
      </AlertDescription>
    </Alert>
  );
}

export function Note({ children, tone = "pend" }: { children: ReactNode; tone?: "pend" | "neutral" }) {
  return (
    <div
      role="note"
      className={`rounded-lg border px-4 py-3 ${
        tone === "pend" ? "border-pend/30 bg-pend-tint text-ink" : "surface text-ink"
      }`}
    >
      {children}
    </div>
  );
}
