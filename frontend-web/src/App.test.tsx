// Logins and roles in the web app (D-AUTH-1): the login page for anyone not logged in, each role's
// home and sidebar, "You don't have access" on another role's page, and back to login on a 401.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import type { User } from "./api/types";
import { TooltipProvider } from "./components/ui/tooltip";
import { AuthProvider } from "./lib/auth";

const USERS: Record<string, User> = {
  provider: { username: "provider1", display_name: "Gregory Hernandez, DPT", role: "provider", provider_id: "2829620345" },
  reviewer: { username: "reviewer1", display_name: "Reviewer One", role: "reviewer", provider_id: null },
  admin: { username: "admin", display_name: "Administrator", role: "admin", provider_id: null },
};

type Answer = { status: number; body?: unknown };

function serve(routes: Record<string, Answer>) {
  const calls: { path: string; init?: RequestInit }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input).split("?")[0]!;
      calls.push({ path, init });
      const { status, body } = routes[path] ?? { status: 404, body: { detail: "Not Found" } };
      return new Response(body === undefined ? null : JSON.stringify(body), {
        status,
        headers: { "content-type": "application/json" },
      });
    }),
  );
  return calls;
}

function openAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <TooltipProvider>
          <MemoryRouter initialEntries={[path]}>
            <App />
          </MemoryRouter>
        </TooltipProvider>
      </AuthProvider>
    </QueryClientProvider>,
  );
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

describe("logins and roles", () => {
  it("shows the login page to anyone not logged in", async () => {
    serve({ "/v1/auth/me": { status: 401, body: { detail: "Not logged in" } } });
    openAt("/queue");

    expect(await screen.findByRole("heading", { name: "Log in" })).toBeInTheDocument();
    expect(screen.getByLabelText("Username")).toBeInTheDocument();
    expect(screen.queryByText("Review queue")).not.toBeInTheDocument();
  });

  it("lands a reviewer on the review queue, with only a reviewer's pages", async () => {
    serve({
      "/v1/auth/me": { status: 200, body: USERS.reviewer },
      "/v1/review/queue": { status: 200, body: [] },
    });
    openAt("/");

    expect(await screen.findByRole("heading", { name: "Review queue" })).toBeInTheDocument();
    const nav = screen.getAllByRole("list")[0]!;
    expect(within(nav).getByText("Claims")).toBeInTheDocument();
    expect(within(nav).queryByText("Submit claim")).not.toBeInTheDocument();
    expect(within(nav).queryByText("Metrics")).not.toBeInTheDocument();
    expect(screen.getByText("Reviewer One")).toBeInTheDocument();
    expect(screen.getAllByText("Reviewer").length).toBeGreaterThan(0);
  });

  it("lands a provider on My claims and an admin on Overview", async () => {
    serve({ "/v1/auth/me": { status: 200, body: USERS.provider }, "/v1/claims": { status: 200, body: [] } });
    openAt("/");
    expect(await screen.findByRole("heading", { name: "My claims" })).toBeInTheDocument();
    expect(screen.queryByText("Review queue")).not.toBeInTheDocument();
  });

  it("lands an admin on Overview", async () => {
    serve({ "/v1/auth/me": { status: 200, body: USERS.admin } });
    openAt("/");
    expect(await screen.findByRole("heading", { name: "Overview" })).toBeInTheDocument();
  });

  it.each([
    ["provider", "/queue"],
    ["provider", "/claims/CLM-1"],
    ["reviewer", "/metrics"],
    ["reviewer", "/submit"],
    ["admin", "/review/CLM-1"],
    ["admin", "/submit"],
  ])("tells a %s they have no access to %s", async (role, path) => {
    serve({ "/v1/auth/me": { status: 200, body: USERS[role] } });
    openAt(path);
    expect(await screen.findByText("You don't have access")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to your home page" })).toBeInTheDocument();
  });

  it("goes back to the login page when the API answers 401", async () => {
    serve({
      "/v1/auth/me": { status: 200, body: USERS.reviewer },
      "/v1/review/queue": { status: 401, body: { detail: "The session has expired" } },
    });
    openAt("/queue");
    expect(await screen.findByRole("heading", { name: "Log in" })).toBeInTheDocument();
  });

  it("sends no role header: the session cookie says who it is", async () => {
    const calls = serve({
      "/v1/auth/me": { status: 200, body: USERS.reviewer },
      "/v1/review/queue": { status: 200, body: [] },
    });
    openAt("/queue");
    await screen.findByRole("heading", { name: "Review queue" });
    for (const call of calls) {
      expect(JSON.stringify(call.init?.headers ?? {})).not.toMatch(/x-role/i);
      expect(call.init?.credentials).toBe("same-origin");
    }
  });
});
