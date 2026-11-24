import { apiFetch } from "./client";

test("sends JSON and parses the response", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ id: 1 }), { status: 201, headers: { "Content-Type": "application/json" } }));
  await expect(apiFetch("/api/session", { method: "POST", json: { name: "Tess" } })).resolves.toEqual({ id: 1 });
  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toBe("/api/session");
  expect(init?.body).toBe(JSON.stringify({ name: "Tess" }));
  expect(new Headers(init?.headers).get("Content-Type")).toBe("application/json");
});

test("204 resolves to undefined", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
  await expect(apiFetch("/api/session", { method: "DELETE" })).resolves.toBeUndefined();
});

test("errors carry status and detail", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "Not signed in" }), { status: 401 }));
  await expect(apiFetch("/api/me")).rejects.toMatchObject({ status: 401, detail: "Not signed in" });
});

test("an error without a JSON body is still an ApiError", async () => {
  // FastAPI's crash page is plain text, and Vite's proxy answers 502 with no body when the backend is down.
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("Internal Server Error", { status: 500 }));
  await expect(apiFetch("/api/me")).rejects.toMatchObject({ status: 500, message: "Request failed (500)" });
});
