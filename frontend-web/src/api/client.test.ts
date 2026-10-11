import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, onSessionEnded, request } from "./client";

function answer(body: string, type: string, status = 200) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(body, { status, headers: { "content-type": type } })));
}

afterEach(() => vi.unstubAllGlobals());

describe("API client", () => {
  it("returns JSON from a JSON endpoint", async () => {
    answer('{"ok": true}', "application/json");

    await expect(request("/v1/x")).resolves.toEqual({ ok: true });
  });

  it("treats the web app's own page in place of JSON as an error, not data", async () => {
    answer("<!doctype html><html></html>", "text/html");

    await expect(request("/v1/x")).rejects.toThrow(/not forwarding/);
  });

  it("returns text from a text endpoint", async () => {
    answer("<article>explained</article>", "text/html");

    await expect(request("/v1/x", { expect: "text" })).resolves.toBe("<article>explained</article>");
  });

  it("turns an API error into plain words with its detail", async () => {
    answer('{"detail": "claim CLM-1 not found"}', "application/json", 404);

    const error = await request("/v1/x").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).toBe("Not found: claim CLM-1 not found");
  });

  it("explains an unreachable API", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));

    await expect(request("/v1/x")).rejects.toThrow(/make demo-up is still running/);
  });

  it("ends the session on a 401, except for a wrong password at login", async () => {
    const ended = vi.fn();
    onSessionEnded(ended);
    answer('{"detail": "Not logged in"}', "application/json", 401);

    await expect(request("/v1/claims")).rejects.toThrow(/log in again/i);
    expect(ended).toHaveBeenCalledTimes(1);
    await expect(request("/v1/auth/login", { method: "POST", json: {} })).rejects.toThrow();
    expect(ended).toHaveBeenCalledTimes(1);
    onSessionEnded(null);
  });

  it("answers nothing for 204 No Content (logout)", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 204 })));

    await expect(request("/v1/auth/logout", { method: "POST" })).resolves.toBeUndefined();
  });
});
