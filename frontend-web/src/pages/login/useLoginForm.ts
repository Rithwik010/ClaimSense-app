// The login logic (D-AUTH-1): the form's values, the submit that logs in and opens the page asked
// for (when the role may open it) or the role's home, the error, and what the form shows while it
// is filled in: caps lock, the password shown or hidden, and an empty field (D-UI-11).

import { useState, type FormEvent, type KeyboardEvent } from "react";
import { useLocation, useNavigate } from "react-router";

import { ApiError } from "@/api/client";
import type { Role } from "@/api/types";
import { PAGES, homeFor, useAuth } from "@/lib/auth";

/** The page the user asked for before logging in, if their role may open it. */
export function destination(from: string | undefined, role: Role): string {
  if (!from || from === "/" || from === "/login") return homeFor(role);
  const page = PAGES.find((p) => from === p.to || from.startsWith(`${p.to}/`));
  const allowed =
    (page && page.roles.includes(role)) || (from.startsWith("/review/") && role === "reviewer");
  return allowed ? from : homeFor(role);
}

export function useLoginForm() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const { state } = useLocation();
  const from = (state as { from?: string } | null)?.from;
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);
  const [capsLock, setCapsLock] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [missing, setMissing] = useState({ username: false, password: false });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const gaps = { username: !username.trim(), password: !password };
    setMissing(gaps);
    if (gaps.username || gaps.password) {
      const empty = event.currentTarget.elements.namedItem(gaps.username ? "username" : "password");
      if (empty instanceof HTMLInputElement) empty.focus();
      return;
    }
    setPending(true);
    setError(null);
    login(username.trim(), password)
      .then((who) => navigate(destination(from, who.role), { replace: true }))
      .catch((reason: unknown) => setError(reason))
      .finally(() => setPending(false));
  }

  return {
    user,
    from,
    username,
    password,
    error,
    wrong: error instanceof ApiError && error.status === 401,
    pending,
    submit,
    missing,
    capsLock,
    showPassword,
    changeUsername(value: string) {
      setUsername(value);
      if (missing.username) setMissing((m) => ({ ...m, username: false }));
    },
    changePassword(value: string) {
      setPassword(value);
      if (missing.password) setMissing((m) => ({ ...m, password: false }));
    },
    /** Caps lock, read from each key press in a field. */
    trackCaps(event: KeyboardEvent<HTMLInputElement>) {
      setCapsLock(event.getModifierState("CapsLock"));
    },
    toggleShowPassword() {
      setShowPassword((shown) => !shown);
    },
  };
}

export type LoginFormState = ReturnType<typeof useLoginForm>;
