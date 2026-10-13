// Login, the only public page (D-AUTH-1): username and password. After logging in, the page asked
// for (when the role may open it) or the role's home. Wide screens also show what ClaimSense
// does, with the pipeline drawn as a slow beam of light.

import { ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";

import { ApiError } from "@/api/client";
import type { Role } from "@/api/types";
import { BlurFade, LogoMark, PipelineBeam, Wordmark } from "@/components/fx";
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
    <main className="relative grid min-h-svh lg:grid-cols-[1.1fr_1fr]">
      {/* The story of a claim, for the wide screen: wordmark, one line, the pipeline. */}
      <section aria-label="About ClaimSense" className="relative hidden flex-col justify-between overflow-hidden px-12 py-12 lg:flex xl:px-16">
        <span
          aria-hidden
          className="pointer-events-none absolute -top-40 -left-32 size-[34rem] rounded-full bg-[radial-gradient(circle,rgb(67_97_238/0.35),transparent_65%)] blur-2xl"
        />
        <span
          aria-hidden
          className="pointer-events-none absolute right-0 bottom-0 size-[28rem] rounded-full bg-[radial-gradient(circle,rgb(34_211_238/0.14),transparent_65%)] blur-2xl"
        />
        <BlurFade className="relative flex items-center gap-3">
          <LogoMark size={36} />
          <Wordmark className="text-[22px]" />
        </BlurFade>
        <div className="relative max-w-[560px]">
          <BlurFade delay={0.08}>
            <h2 className="text-glow text-[40px] leading-[48px] font-semibold tracking-[-0.03em] xl:text-[46px] xl:leading-[54px]">
              Claims checked by rules, explained by a model, decided by people.
            </h2>
          </BlurFade>
          <BlurFade delay={0.16}>
            <p className="mt-5 max-w-[48ch] text-[17px] leading-7 text-ink-muted">
              Every recommendation shows its evidence. A reviewer accepts or overrides each line, and every step
              is recorded.
            </p>
          </BlurFade>
          <BlurFade delay={0.24} className="mt-12">
            <PipelineBeam />
          </BlurFade>
        </div>
        <p className="relative flex items-center gap-2 text-[13px] text-ink-muted">
          <ShieldCheck aria-hidden className="size-4 text-glow-cyan" />
          Prototype · synthetic data only
        </p>
      </section>

      <div className="relative grid place-items-center px-4 py-10 sm:px-8">
        <BlurFade delay={0.1} className="w-full max-w-[420px]">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <LogoMark size={32} />
            <Wordmark className="text-[20px]" />
          </div>
          <form
            className="glass edge-light rounded-xl p-7 sm:p-8"
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
            <h1 className="mb-1 text-[28px] leading-9 font-semibold tracking-[-0.02em]">Log in</h1>
            <p className="mb-7 text-ink-muted">Synthetic data only. Not for real claims.</p>
            <label className="mb-5 grid gap-2 text-[14px] font-semibold" htmlFor="username">
              Username
              <Input
                id="username"
                name="username"
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                required
                value={username}
                className="h-11 rounded-md px-3 text-[15px] font-normal"
                onChange={(event) => setUsername(event.target.value)}
              />
            </label>
            <label className="mb-6 grid gap-2 text-[14px] font-semibold" htmlFor="password">
              Password
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                className="h-11 rounded-md px-3 text-[15px] font-normal"
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            {error !== null &&
              (wrong ? (
                <p role="alert" className="mb-4 rounded-md border border-deny/30 bg-deny-tint px-3 py-2 text-deny">
                  Wrong username or password. Check both and try again.
                </p>
              ) : (
                <div className="mb-4">
                  <ErrorNotice error={error} />
                </div>
              ))}
            <Button type="submit" size="lg" className="h-11 w-full text-[15px]" disabled={pending || !username || !password}>
              {pending ? "Logging in" : "Log in"}
            </Button>
          </form>
          <p className="mt-6 text-center text-[13px] text-ink-muted lg:hidden">Prototype · synthetic data only</p>
        </BlurFade>
      </div>
    </main>
  );
}
