import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { renderWithProviders } from "../test/render";
import RequireUser from "./RequireUser";

vi.mock("../api/client", async (orig) => ({ ...(await orig<typeof import("../api/client")>()), getMe: vi.fn() }));
import { ApiError, getMe } from "../api/client";

test("redirects to the role picker when not signed in", async () => {
  vi.mocked(getMe).mockRejectedValue(new ApiError(401, "Not signed in"));
  renderWithProviders(
    <Routes>
      <Route path="/" element={<RequireUser><p>secret</p></RequireUser>} />
      <Route path="/start" element={<p>pick a role</p>} />
    </Routes>);
  expect(await screen.findByText("pick a role")).toBeInTheDocument();
  expect(getMe).toHaveBeenCalledTimes(1); // a 4xx is never retried
});

test("when the server can't be reached, Retry asks again", async () => {
  // What apiFetch throws when Vite's proxy answers 502 because the backend is down.
  vi.mocked(getMe).mockRejectedValue(new ApiError(502, undefined));
  renderWithProviders(<RequireUser><p>secret</p></RequireUser>);
  expect(await screen.findByText(/can't reach the server/i)).toBeInTheDocument();
  expect(getMe).toHaveBeenCalledTimes(4); // the first try and 3 retries

  vi.mocked(getMe).mockResolvedValue({ id: 1, name: "Tess", role: "tech", email: null });
  await userEvent.click(screen.getByRole("button", { name: /retry/i }));
  expect(await screen.findByText("secret")).toBeInTheDocument();
});

test("shows nothing until it knows who you are", async () => {
  vi.mocked(getMe).mockReturnValue(new Promise(() => {})); // never answers
  renderWithProviders(<RequireUser><p>secret</p></RequireUser>);
  await new Promise((resolve) => setTimeout(resolve, 50)); // give it time to (wrongly) render
  expect(screen.queryByText("secret")).toBeNull();
});
