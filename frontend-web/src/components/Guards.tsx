// Route guards (D-AUTH-1): every page but the login page needs a logged-in user; each page is for
// some roles only, and another role's URL shows "You don't have access" instead of the page.

import { Link, Navigate, Outlet, useLocation } from "react-router";

import type { Role } from "@/api/types";
import { EmptyState, Skeleton } from "@/components/States";
import { ROLE_LABELS, homeFor, useAuth, useUser } from "@/lib/auth";

export function RequireLogin() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div className="mx-auto max-w-md p-8">
        <Skeleton lines={3} />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}

export function Allow({ roles }: { roles: Role[] }) {
  const { role } = useUser();
  return roles.includes(role) ? <Outlet /> : <NoAccess roles={roles} />;
}

/** "/" and a fresh login go to the role's home page. */
export function Home() {
  return <Navigate to={homeFor(useUser().role)} replace />;
}

export function NoAccess({ roles }: { roles: Role[] }) {
  const user = useUser();
  const who = roles.map((role) => ROLE_LABELS[role].toLowerCase()).join(" or ");
  return (
    <EmptyState title="You don't have access">
      <p>
        This page is for a {who}. You are logged in as {user.display_name} ({ROLE_LABELS[user.role].toLowerCase()}).
      </p>
      <p className="mt-3">
        <Link className="font-semibold text-ink underline underline-offset-4" to={homeFor(user.role)}>
          Go to your home page
        </Link>
      </p>
    </EmptyState>
  );
}
