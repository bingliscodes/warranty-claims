import type { Me, Role } from "./types";

/** A non-2xx answer from the backend. `detail` is the `detail` field of FastAPI's error body. */
export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(messageFrom(status, detail));
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

// FastAPI sends `detail` as a string for errors our routes raise ("Not signed in"), and as a list
// of {loc, msg, ...} for a 422 from request validation. The message is what a form's alert shows.
function messageFrom(status: number, detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((item) => item?.msg)
      .filter((msg) => typeof msg === "string");
    if (msgs.length > 0) return msgs.join("; ");
  }
  return `Request failed (${status})`;
}

/**
 * Calls the backend. Every request in the app goes through here.
 * - `path` is relative (`/api/...`): same origin, so the session cookie goes along.
 * - `json`, when given, is sent as the body with a `Content-Type: application/json` header.
 * - A 204 resolves to `undefined`. Any other 2xx resolves to the parsed JSON body.
 * - Any other status throws `ApiError(status, detail)`, with `detail` taken from the body.
 */
export async function apiFetch<T>(
  path: string,
  options: { method?: string; json?: unknown } = {},
): Promise<T> {
  const hasBody = options.json !== undefined;
  const res = await fetch(path, {
    method: options.method ?? "GET",
    credentials: "same-origin",
    headers: hasBody ? { "Content-Type": "application/json" } : undefined,
    body: hasBody ? JSON.stringify(options.json) : undefined,
  });

  if (res.status === 204) return undefined as T;

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, body?.detail);
  }

  return (await res.json()) as T;
}

// Session calls (Task 3's /api/session and /api/me). Later tasks add their endpoints below.

export function createSession(body: {
  name: string;
  role: Role;
  email?: string | null;
}): Promise<Me> {
  return apiFetch<Me>("/api/session", { method: "POST", json: body });
}

export function endSession(): Promise<void> {
  return apiFetch<void>("/api/session", { method: "DELETE" });
}

export function getMe(): Promise<Me> {
  return apiFetch<Me>("/api/me");
}

export function updateMe(body: {
  name?: string;
  email?: string | null;
}): Promise<Me> {
  return apiFetch<Me>("/api/me", { method: "PATCH", json: body });
}
