// The login form (D-AUTH-1, D-UI-11): username, password with a Show/Hide toggle, Log in. It shows
// each state: empty (a message on the empty field, never a disabled button), wrong username or
// password, logging in (the button disabled with a spinner) and caps lock on. Keyboard order:
// username, password, Show/Hide, Log in.

import { ArrowBigUpDash, CircleAlert, LoaderCircle } from "lucide-react";
import { useId } from "react";

import { ErrorNotice } from "@/components/States";
import { cn } from "@/lib/utils";

import type { LoginFormState } from "./useLoginForm";

const FIELD =
  "h-11 w-full rounded-md border border-control bg-white px-3 text-[15px] text-ink outline-none transition-colors hover:border-ink-muted focus-visible:border-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary aria-invalid:border-deny";
const LABEL = "text-[14px] leading-5 font-semibold text-ink";
const MISSING = "text-[13px] leading-5 font-semibold text-deny";

export function LoginForm({ form, intro, className }: { form: LoginFormState; intro?: string; className?: string }) {
  const id = useId();
  const ids = {
    username: `${id}username`,
    password: `${id}password`,
    caps: `${id}caps`,
    usernameMissing: `${id}username-missing`,
    passwordMissing: `${id}password-missing`,
  };

  return (
    <form noValidate onSubmit={form.submit} aria-busy={form.pending} className={cn("flex flex-col gap-5", className)}>
      <div>
        <h1 className="font-heading text-[30px] leading-9 font-bold text-ink-strong">Log in</h1>
        {intro && <p className="mt-1.5 text-[15px] leading-6 text-ink-muted">{intro}</p>}
      </div>

      {form.error !== null &&
        (form.wrong ? (
          <p
            role="alert"
            className="flex gap-2 rounded-md border border-deny/30 bg-deny-tint px-3 py-2.5 text-[14px] leading-5 text-deny"
          >
            <CircleAlert aria-hidden className="mt-px size-4 shrink-0" />
            Wrong username or password. Check both and try again.
          </p>
        ) : (
          <ErrorNotice error={form.error} />
        ))}

      <div className="grid gap-2">
        <label htmlFor={ids.username} className={LABEL}>
          Username
        </label>
        <input
          id={ids.username}
          name="username"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          aria-required="true"
          aria-invalid={form.missing.username || undefined}
          aria-describedby={form.missing.username ? ids.usernameMissing : undefined}
          value={form.username}
          onChange={(event) => form.changeUsername(event.target.value)}
          onKeyDown={form.trackCaps}
          onKeyUp={form.trackCaps}
          className={FIELD}
        />
        {form.missing.username && (
          <p id={ids.usernameMissing} className={MISSING}>
            Enter your username.
          </p>
        )}
      </div>

      <div className="grid gap-2">
        <label htmlFor={ids.password} className={LABEL}>
          Password
        </label>
        <div className="relative">
          <input
            id={ids.password}
            name="password"
            type={form.showPassword ? "text" : "password"}
            autoComplete="current-password"
            aria-required="true"
            aria-invalid={form.missing.password || undefined}
            aria-describedby={
              [form.capsLock && ids.caps, form.missing.password && ids.passwordMissing].filter(Boolean).join(" ") ||
              undefined
            }
            value={form.password}
            onChange={(event) => form.changePassword(event.target.value)}
            onKeyDown={form.trackCaps}
            onKeyUp={form.trackCaps}
            className={cn(FIELD, "pr-20")}
          />
          <button
            type="button"
            aria-controls={ids.password}
            aria-pressed={form.showPassword}
            onClick={form.toggleShowPassword}
            className="absolute top-1/2 right-1.5 h-8 -translate-y-1/2 rounded px-2.5 text-[14px] font-semibold text-primary transition-colors hover:bg-brand-tint focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-primary"
          >
            {form.showPassword ? "Hide" : "Show"}
          </button>
        </div>
        <p
          id={ids.caps}
          role="status"
          className={
            form.capsLock
              ? "flex items-center gap-1.5 rounded-md bg-brand-tint px-2.5 py-1.5 text-[13px] leading-5 font-semibold text-ink-strong"
              : "sr-only"
          }
        >
          {form.capsLock && (
            <>
              <ArrowBigUpDash aria-hidden className="size-4 shrink-0" />
              Caps Lock is on.
            </>
          )}
        </p>
        {form.missing.password && (
          <p id={ids.passwordMissing} className={MISSING}>
            Enter your password.
          </p>
        )}
      </div>

      <button
        type="submit"
        disabled={form.pending}
        className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-md bg-primary text-[15px] font-semibold text-white transition-[background-color,transform] duration-150 hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary active:scale-[0.98] disabled:cursor-progress disabled:bg-primary-hover"
      >
        {form.pending ? (
          <>
            <LoaderCircle aria-hidden className="size-[18px] animate-spin" />
            Logging in
          </>
        ) : (
          "Log in"
        )}
      </button>

      <p className="text-[13px] leading-5 text-ink-muted">Trouble signing in? Contact your administrator.</p>
    </form>
  );
}
