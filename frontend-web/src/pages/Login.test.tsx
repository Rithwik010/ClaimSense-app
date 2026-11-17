// The login page (D-AUTH-1, D-UI-11): written for a member first, nothing about how claims are
// processed inside; an empty field gets a message instead of a disabled button; a wrong username
// or password says so; the password can be shown; logging in opens the role's home.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import type { User } from "../api/types";
import { TooltipProvider } from "../components/ui/tooltip";
import { AuthProvider } from "../lib/auth";

const MEMBER: User = {
  username: "member1",
  display_name: "A Member",
  role: "member",
  provider_id: null,
  member_id: "MBR-000001",
};

type Answer = { status: number; body?: unknown };

function serve(routes: Record<string, Answer>) {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input).split("?")[0]!;
      calls.push(path);
      const { status, body } = routes[path] ?? { status: 404, body: { detail: "Not Found" } };
      return new Response(body === undefined ? null : JSON.stringify(body), {
        status,
        headers: { "content-type": "application/json" },
      });
    }),
  );
  return calls;
}

async function openLogin(routes: Record<string, Answer> = {}) {
  const calls = serve({ "/v1/auth/me": { status: 401, body: { detail: "Not logged in" } }, ...routes });
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <AuthProvider>
        <TooltipProvider>
          <MemoryRouter initialEntries={["/login"]}>
            <App />
          </MemoryRouter>
        </TooltipProvider>
      </AuthProvider>
    </QueryClientProvider>,
  );
  await screen.findByRole("heading", { name: "Log in" });
  return calls;
}

beforeEach(() => {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
});
afterEach(() => vi.unstubAllGlobals());

describe("the login page", () => {
  it("speaks to a member and says nothing about the processing inside", async () => {
    await openLogin();
    expect(screen.getByRole("heading", { name: "Your claims, clearly explained." })).toBeInTheDocument();
    expect(screen.getByText("Understand every decision in plain words")).toBeInTheDocument();
    expect(screen.getByText("A person reviews every recommendation")).toBeInTheDocument();
    expect(screen.getByText("Trouble signing in? Contact your administrator.")).toBeInTheDocument();
    for (const internal of [/model/i, /pipeline/i, /intake/i, /audit/i, /calculator/i]) {
      expect(screen.queryByText(internal)).not.toBeInTheDocument();
    }
  });

  it("asks for an empty field instead of logging in", async () => {
    const calls = await openLogin();
    const user = userEvent.setup();
    const button = screen.getByRole("button", { name: "Log in" });
    expect(button).toBeEnabled();

    await user.click(button);
    expect(screen.getByText("Enter your username.")).toBeInTheDocument();
    expect(screen.getByLabelText("Username")).toHaveFocus();
    expect(screen.getByLabelText("Username")).toHaveAttribute("aria-invalid", "true");

    await user.type(screen.getByLabelText("Username"), "member1");
    expect(screen.queryByText("Enter your username.")).not.toBeInTheDocument();
    await user.click(button);
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toHaveFocus();
    expect(calls).not.toContain("/v1/auth/login");
  });

  it("says when the username or password is wrong", async () => {
    await openLogin({ "/v1/auth/login": { status: 401, body: { detail: "Wrong username or password" } } });
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Username"), "member1");
    await user.type(screen.getByLabelText("Password"), "not-the-password");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Wrong username or password. Check both and try again.");
  });

  it("shows and hides the password, after it in the keyboard order", async () => {
    await openLogin();
    const user = userEvent.setup();
    const password = screen.getByLabelText("Password");
    expect(password).toHaveAttribute("type", "password");

    await user.tab();
    expect(screen.getByLabelText("Username")).toHaveFocus();
    await user.tab();
    expect(password).toHaveFocus();
    await user.tab();
    const toggle = screen.getByRole("button", { name: "Show" });
    expect(toggle).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "Log in" })).toHaveFocus();

    await user.click(toggle);
    expect(password).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: "Hide" })).toHaveAttribute("aria-pressed", "true");
  });

  it("logs a member in and opens their claims", async () => {
    const calls = await openLogin({
      "/v1/auth/login": { status: 200, body: MEMBER },
      "/v1/member/claims": { status: 200, body: [] },
    });
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Username"), "  member1 ");
    await user.type(screen.getByLabelText("Password"), "the-password");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    expect(await screen.findByRole("heading", { name: "My claims" })).toBeInTheDocument();
    await waitFor(() => expect(calls).toContain("/v1/member/claims"));
    expect(screen.queryByRole("heading", { name: "Log in" })).not.toBeInTheDocument();
  });
});
