// Login, the only public page (D-AUTH-1): username and password. After logging in, the page asked
// for (when the role may open it) or the role's home. The page (D-UI-9, the canvas's login design
// 3): a blue band with the claim's journey, and a card over it with the form and what ClaimSense is.

import { Check } from "lucide-react";
import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";

import { ApiError } from "@/api/client";
import type { Role } from "@/api/types";
import { BlurFade, LogoMark, Wordmark } from "@/components/fx";
import { ErrorNotice } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PAGES, homeFor, useAuth } from "@/lib/auth";

const STAGES = ["Intake", "Rules", "Policy", "Model", "Amounts", "Explanation", "Review", "Audit"];
const PROMISES = [
  "Every recommendation goes to a person",
  "Amounts come only from the calculator, never the model",
  "Every step is audited",
];

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
    <main className="min-h-svh bg-white">
      <header className="flex h-16 items-center gap-3 border-b border-rules px-4 md:h-[72px] md:px-16">
        <LogoMark size={36} />
        <Wordmark className="text-[26px] text-ink-strong md:text-[28px]" />
      </header>
      {/* The claim's journey, on the blue band (D-UI-9): the pipeline's steps, the review step marked. */}
      <section aria-labelledby="login-story" className="bg-sidebar px-4 pt-7 pb-28 text-white md:px-16 md:pt-11 md:pb-32">
        <h2 id="login-story" className="max-w-[900px] text-[31px] leading-[1.15] font-bold text-white md:text-[52px] md:leading-[1.1]">
          From claim to decision, every step on the record.
        </h2>
        <p className="mt-3 text-[15px] text-[#e6ebff] md:hidden">Rules, evidence from the notes, and a person decides.</p>
        <ol aria-label="The pipeline" className="mt-6 hidden flex-wrap items-center gap-2 md:flex">
          {STAGES.map((stage, i) => (
            <li key={stage} className="flex items-center gap-2">
              <span
                className={`rounded-full px-3.5 py-1.5 text-[14px] whitespace-nowrap ${
                  stage === "Review" ? "bg-white font-bold text-primary" : "border border-[#ccd6ff] text-white"
                }`}
              >
                {i + 1}. {stage}
              </span>
              {i < STAGES.length - 1 && (
                <span aria-hidden className="text-[#ccd6ff]">
                  ›
                </span>
              )}
            </li>
          ))}
        </ol>
      </section>

      <div className="relative z-10 mx-4 -mt-20 mb-10 md:mx-16 md:-mt-24">
        <BlurFade className="mx-auto grid max-w-[1152px] overflow-hidden rounded-xl border border-rules bg-white shadow-lg lg:grid-cols-2">
          <form
            className="p-6 sm:p-9 lg:px-12"
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
            <h1 className="mb-1.5 text-[32px] leading-10 font-bold md:text-[34px]">Log in</h1>
            <p className="mb-6 text-[15px] text-ink-muted">
              Providers, reviewers, admins and members each land on their own pages.
            </p>
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
          <aside
            aria-label="About ClaimSense"
            className="hidden flex-col gap-5 border-t border-rules p-6 sm:flex sm:p-9 lg:border-t-0 lg:border-l lg:px-12"
          >
            <div className="rounded-lg bg-brand-tint p-5">
              <p className="text-[13px] font-bold tracking-[0.06em] text-ink-strong uppercase">New: model v3</p>
              <p className="mt-2 font-heading text-[24px] leading-8 font-bold text-ink-strong">Reads real-world, messy notes</p>
              <p className="mt-1.5 text-[15px] leading-6">
                Trained on notes written the way clinicians write them: abbreviations, typos and text copied from
                earlier visits. Its results against model v2 are on the admin's Model metrics page.
              </p>
            </div>
            <ul className="flex flex-col gap-3 text-[15px]">
              {PROMISES.map((text) => (
                <li key={text} className="flex items-center gap-2.5">
                  <Check aria-hidden className="size-[18px] shrink-0 text-primary" strokeWidth={2.6} />
                  {text}
                </li>
              ))}
            </ul>
          </aside>
        </BlurFade>
      </div>
    </main>
  );
}
