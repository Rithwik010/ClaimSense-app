// The person using the app: their role (sent as X-Role) and reviewer ID, remembered in this
// browser only (a convenience; the API records the reviewer ID with each review).

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

import type { Role } from "../api/types";

interface Session {
  role: Role;
  reviewerId: string;
  setRole: (role: Role) => void;
  setReviewerId: (id: string) => void;
}

const KEYS = { role: "claimsense.role", reviewerId: "claimsense.reviewerId" };
const ROLES: Role[] = ["provider", "reviewer", "admin"];

function remembered(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function remember(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Storage may be blocked (private window); the value then lasts for this page only.
  }
}

const SessionContext = createContext<Session | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const stored = remembered(KEYS.role);
  const [role, setRoleState] = useState<Role>(
    ROLES.includes(stored as Role) ? (stored as Role) : "reviewer",
  );
  const [reviewerId, setReviewerIdState] = useState(remembered(KEYS.reviewerId) ?? "");
  const value = useMemo<Session>(
    () => ({
      role,
      reviewerId,
      setRole: (next) => {
        setRoleState(next);
        remember(KEYS.role, next);
      },
      setReviewerId: (next) => {
        setReviewerIdState(next);
        remember(KEYS.reviewerId, next);
      },
    }),
    [role, reviewerId],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (!session) throw new Error("useSession needs a SessionProvider");
  return session;
}
