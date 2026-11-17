// The logged-in user (D-AUTH-1). The session is an httpOnly cookie the API sets at login, so the
// app never sees the token: it asks /v1/auth/me who is logged in. Each role has its own pages and
// home; any 401 from the API ends the session and shows the login page. A member (a patient,
// D-MEM-1) has only their own pages, under /member.

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  BarChart3,
  BookOpen,
  ClipboardCheck,
  FileText,
  FileUp,
  Files,
  Gauge,
  History,
  IdCard,
  Inbox,
  LayoutDashboard,
  Scale,
  ShieldPlus,
  UsersRound,
  type LucideIcon,
} from "lucide-react";
import { createContext, useContext, useEffect, useMemo, type ReactNode } from "react";

import { ApiError, onSessionEnded, request } from "@/api/client";
import type { Role, User } from "@/api/types";

export const ROLE_LABELS: Record<Role, string> = {
  provider: "Provider",
  reviewer: "Reviewer",
  admin: "Admin",
  member: "Member",
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
  { to: "/rule-outcomes", label: "Returned and auto-denied", icon: Scale, roles: ["reviewer", "admin"] },
  { to: "/policies", label: "Coverage policies", icon: BookOpen, roles: ["provider", "reviewer", "admin"] },
  { to: "/quality", label: "Review quality", icon: Gauge, roles: ["admin"] },
  { to: "/metrics", label: "Model metrics", icon: BarChart3, roles: ["admin"] },
  { to: "/audit", label: "Audit lookup", icon: History, roles: ["admin"] },
  { to: "/users", label: "Users", icon: UsersRound, roles: ["admin"] },
  { to: "/system", label: "System status", icon: Activity, roles: ["admin"] },
  { to: "/member/claims", label: "My claims", icon: Inbox, roles: ["member"] },
  { to: "/member/benefits", label: "My benefits", icon: ShieldPlus, roles: ["member"] },
  { to: "/member/plan", label: "My plan", icon: FileText, roles: ["member"] },
  { to: "/member/profile", label: "Profile", icon: IdCard, roles: ["member"] },
];

const HOMES: Record<Role, string> = {
  provider: "/my-claims",
  reviewer: "/queue",
  admin: "/overview",
  member: "/member/claims",
};

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
