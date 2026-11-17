// Single-key shortcuts for a page (the reviewer's, D-REV-10): a key without Ctrl, Alt or Meta, not
// while typing in a field or while a dialog or side sheet is open. Each page lists its keys where
// the reviewer sees them.

import { useEffect, useRef } from "react";

function typing(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return (
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    tag === "SELECT" ||
    target.isContentEditable ||
    target.closest("[role='dialog'], [role='listbox'], [role='menu']") !== null
  );
}

export function useShortcuts(keys: Record<string, () => void>, enabled = true): void {
  const latest = useRef(keys);
  useEffect(() => {
    latest.current = keys;
  });
  useEffect(() => {
    if (!enabled) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.ctrlKey || event.altKey || event.metaKey || event.repeat || typing(event.target)) return;
      if (document.querySelector("[role='dialog'][data-state='open']")) return;
      const action = latest.current[event.key.toLowerCase()];
      if (!action) return;
      event.preventDefault();
      action();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [enabled]);
}
