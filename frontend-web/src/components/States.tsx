// Loading skeletons, empty states and API errors in plain words.

import type { ReactNode } from "react";

import { button } from "./ui";

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div role="status" aria-label="Loading" className="space-y-3">
      {Array.from({ length: lines }, (_, i) => (
        <div
          key={i}
          className="h-4 rounded bg-gray-100 motion-safe:animate-pulse"
          style={{ width: `${90 - i * 12}%` }}
        />
      ))}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-gray-300 px-6 py-10 text-center">
      <p className="font-medium text-gray-800">{title}</p>
      {children && <div className="mt-2 text-gray-600">{children}</div>}
    </div>
  );
}

export function ErrorNotice({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-800">
      <p>{message}</p>
      {onRetry && (
        <button type="button" className={`${button.secondary} mt-3`} onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}
