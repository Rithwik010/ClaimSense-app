// Login, the only public page (D-AUTH-1): username and password. After logging in, the page asked
// for (when the role may open it) or the role's home.

import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";

import { ApiError } from "@/api/client";
import type { Role } from "@/api/types";
import { ErrorNotice } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PAGES, homeFor, useAuth } from "@/lib/auth";

/** The page the user asked for before logging in, if their role may open it. */
function destination(from: string | undefined, role: Role): string {
  if (!from || from === "/" || from === "/login") return homeFor(role);
  const page = PAGES.find((p) => from === p.to || from.startsWith(`${p.to}/`));
  const allowed =
    (page && page.roles.includes(role)) || (from.startsWith("/review/") && role === "reviewer");
  return allowed ? from : homeFor(role);
}

export function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const { state } = useLocation();
  const from = (state as { from?: string } | null)?.from;
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  if (user) return <Navigate to={destination(from, user.role)} replace />;
  const wrong = error instanceof ApiError && error.status === 401;

  return (
    <main className="grid min-h-svh place-items-center bg-canvas px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-2">
          <span
            aria-hidden
            className="grid size-7 place-items-center rounded-md bg-ink text-[13px] font-semibold text-white"
          >
            C
          </span>
          <span className="text-[18px] font-semibold">ClaimSense</span>
        </div>
        <form
          className="rounded-lg border border-rules bg-paper p-6"
          onSubmit={(event) => {
            event.preventDefault();
            setPending(true);
            setError(null);
            login(username.trim(), password)
              .then((who) => navigate(destination(from, who.role), { replace: true }))
              .catch((reason: unknown) => setError(reason))
              .finally(() => setPending(false));
          }}
        >
          <h1 className="mb-1 text-[24px] leading-8 font-semibold">Log in</h1>
          <p className="mb-5 text-ink-muted">Synthetic data only. Not for real claims.</p>
          <label className="mb-4 grid gap-1.5 font-semibold" htmlFor="username">
            Username
            <Input
              id="username"
              name="username"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              required
              value={username}
              className="h-10 bg-paper font-normal"
              onChange={(event) => setUsername(event.target.value)}
            />
          </label>
          <label className="mb-5 grid gap-1.5 font-semibold" htmlFor="password">
            Password
            <Input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              className="h-10 bg-paper font-normal"
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          {error !== null &&
            (wrong ? (
              <p role="alert" className="mb-4 text-deny">
                Wrong username or password. Check both and try again.
              </p>
            ) : (
              <div className="mb-4">
                <ErrorNotice error={error} />
              </div>
            ))}
          <Button type="submit" size="lg" className="w-full" disabled={pending || !username || !password}>
            {pending ? "Logging in" : "Log in"}
          </Button>
        </form>
      </div>
    </main>
  );
}
