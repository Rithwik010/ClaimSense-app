import { NavLink, Outlet } from "react-router";

import type { Role } from "../api/types";
import { useSession } from "../lib/session";
import { input } from "./ui";

const NAV = [
  { to: "/submit", label: "Submit claim" },
  { to: "/queue", label: "Review queue" },
  { to: "/claims", label: "Claims" },
  { to: "/rule-outcomes", label: "Rule outcomes" },
  { to: "/metrics", label: "Metrics" },
];

const ROLES: { value: Role; label: string }[] = [
  { value: "provider", label: "Provider" },
  { value: "reviewer", label: "Reviewer" },
  { value: "admin", label: "Admin" },
];

export function Layout() {
  const { role, setRole, reviewerId, setReviewerId } = useSession();
  return (
    <div className="min-h-screen">
      <header className="flex flex-wrap items-center gap-x-8 gap-y-3 border-b border-gray-200 px-6 py-3">
        <span className="text-lg font-semibold tracking-tight">ClaimSense</span>
        <span className="text-sm text-gray-600">Synthetic data only</span>
        <div className="ml-auto flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-gray-700">
            Role
            <select
              className={`${input} w-auto py-1.5`}
              value={role}
              onChange={(event) => setRole(event.target.value as Role)}
            >
              {ROLES.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 whitespace-nowrap text-sm text-gray-700">
            Reviewer ID
            <input
              className={`${input} w-40 py-1.5`}
              value={reviewerId}
              placeholder="e.g. reviewer-1"
              onChange={(event) => setReviewerId(event.target.value)}
            />
          </label>
        </div>
      </header>
      <div className="flex">
        <nav aria-label="Main" className="w-52 shrink-0 border-r border-gray-200 px-3 py-6">
          <ul className="space-y-1">
            {NAV.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  className={({ isActive }) =>
                    `block rounded-md px-3 py-2 transition-colors duration-150 ${
                      isActive
                        ? "bg-accent-soft font-medium text-accent-strong"
                        : "text-gray-700 hover:bg-gray-50"
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <main className="min-w-0 flex-1 px-8 py-8">
          <div className="mx-auto max-w-6xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}

export function PageTitle({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="mb-6">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      {hint && <p className="mt-1 text-gray-600">{hint}</p>}
    </div>
  );
}

export function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-8">
      <h2 className="mb-3 text-lg font-semibold">{title}</h2>
      {children}
    </section>
  );
}
