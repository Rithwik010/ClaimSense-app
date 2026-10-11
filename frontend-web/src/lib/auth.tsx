// The logged-in user (D-AUTH-1). The session is an httpOnly cookie the API sets at login, so the
// app never sees the token: it asks /v1/auth/me who is logged in. Each role has its own pages and
// home; any 401 from the API ends the session and shows the login page.

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BarChart3,
  ClipboardCheck,
  FileUp,
  Files,
  Inbox,
  LayoutDashboard,
  Scale,
  type LucideIcon,
} from "lucide-react";
import { createContext, useContext, useEffect, useMemo, type ReactNode } from "react";

import { ApiError, onSessionEnded, request } from "@/api/client";
import type { Role, User } from "@/api/types";

export const ROLE_LABELS: Record<Role, string> = {
  provider: "Provider",
  reviewer: "Reviewer",
  admin: "Admin",
};

interface Page {
  to: string;
  label: string;
  icon: LucideIcon;
  roles: Role[];
}

/** Each page and the roles that may open it; the sidebar lists a role's pages in this order. */
export const PAGES: Page[] = [
  { to: "/my-claims", label: "My claims", icon: Inbox, roles: ["provider"] },
  { to: "/submit", label: "Submit claim", icon: FileUp, roles: ["provider"] },
  { to: "/overview", label: "Overview", icon: LayoutDashboard, roles: ["admin"] },
  { to: "/queue", label: "Review queue", icon: ClipboardCheck, roles: ["reviewer", "admin"] },
  { to: "/claims", label: "Claims", icon: Files, roles: ["reviewer", "admin"] },
  { to: "/rule-outcomes", label: "Rule outcomes", icon: Scale, roles: ["reviewer", "admin"] },
  { to: "/metrics", label: "Metrics", icon: BarChart3, roles: ["admin"] },
];

const HOMES: Record<Role, string> = { provider: "/my-claims", reviewer: "/queue", admin: "/overview" };

export function homeFor(role: Role): string {
  return HOMES[role];
}

export function pagesFor(role: Role) {
  return PAGES.filter((page) => page.roles.includes(role));
}

interface Auth {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<Auth | null>(null);
const ME = ["me"];

export function AuthProvider({ children }: { children: ReactNode }) {
  const client = useQueryClient();
  const me = useQuery({
    queryKey: ME,
    queryFn: async () => {
      try {
        return await request<User>("/v1/auth/me");
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    retry: false,
    staleTime: Infinity,
  });

  useEffect(() => {
    // A 401 anywhere: forget the user and every cached answer; the routes show the login page.
    onSessionEnded(() => {
      client.removeQueries({ predicate: (query) => query.queryKey[0] !== ME[0] });
      client.setQueryData(ME, null);
    });
    return () => onSessionEnded(null);
  }, [client]);

  const value = useMemo<Auth>(
    () => ({
      user: me.data ?? null,
      loading: me.isPending,
      login: async (username, password) => {
        const user = await request<User>("/v1/auth/login", {
          method: "POST",
          json: { username, password },
        });
        client.removeQueries({ predicate: (query) => query.queryKey[0] !== ME[0] });
        client.setQueryData(ME, user);
        return user;
      },
      logout: async () => {
        try {
          await request("/v1/auth/logout", { method: "POST" });
        } finally {
          client.removeQueries({ predicate: (query) => query.queryKey[0] !== ME[0] });
          client.setQueryData(ME, null);
        }
      },
    }),
    [client, me.data, me.isPending],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): Auth {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error("useAuth needs an AuthProvider");
  return auth;
}

/** The logged-in user, for pages behind the login (RequireLogin guarantees one). */
export function useUser(): User {
  const { user } = useAuth();
  if (!user) throw new Error("useUser outside a logged-in page");
  return user;
}
