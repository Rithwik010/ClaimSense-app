// Every call to the ClaimSense API. Requests go to /v1 and /health on the web app's own origin
// (the API serves the built app; the Vite dev server proxies to it), so the session cookie goes
// with them (D-AUTH-1). Errors become plain sentences for the page; a 401 ends the session.

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

const STATUS_WORDS: Record<number, string> = {
  400: "The request was not valid",
  401: "Your session has ended. Log in again",
  403: "You don't have access to this",
  404: "Not found",
  409: "This conflicts with the claim's current state",
  422: "The API could not accept this",
  500: "The API ran into an error",
  503: "A service the API needs is not available",
};

function detailText(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const entry = item as { loc?: unknown[]; msg?: string };
        const where = (entry.loc ?? []).filter((part) => part !== "body").join(".");
        return where ? `${where}: ${entry.msg}` : entry.msg;
      })
      .join("; ");
  }
  return "";
}

// Called on any 401 except from logging in itself: the app then shows the login page.
let sessionEnded: (() => void) | null = null;

export function onSessionEnded(handler: (() => void) | null): void {
  sessionEnded = handler;
}

export async function request<T>(
  path: string,
  options: {
    method?: string;
    json?: unknown;
    body?: BodyInit;
    type?: string;
    expect?: "json" | "text"; // what the endpoint answers (default JSON)
  } = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  let body = options.body;
  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.json);
  } else if (options.type) {
    headers["Content-Type"] = options.type;
  }
  let response: Response;
  try {
    response = await fetch(path, {
      method: options.method ?? "GET",
      headers,
      body,
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError(0, "The ClaimSense API cannot be reached. Is it running (make demo-up)?");
  }
  if (response.status === 401 && path !== "/v1/auth/login") sessionEnded?.();
  if (!response.ok) {
    let detail: string;
    try {
      detail = detailText(((await response.json()) as { detail?: unknown }).detail);
    } catch {
      detail = "";
    }
    const words = STATUS_WORDS[response.status] ?? `The API answered ${response.status}`;
    throw new ApiError(response.status, detail ? `${words}: ${detail}` : `${words}.`);
  }
  if (response.status === 204) return undefined as T;
  const kind = response.headers.get("content-type") ?? "";
  if ((options.expect ?? "json") === "text") return (await response.text()) as T;
  if (!kind.includes("application/json")) {
    // The web app's own page came back instead of the API: the dev proxy is not forwarding.
    throw new ApiError(
      0,
      "The API did not answer: the web app is not forwarding to it. Restart with make demo-up.",
    );
  }
  return (await response.json()) as T;
}
