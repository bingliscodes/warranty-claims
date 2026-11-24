import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/render";
import ProfilePage from "./ProfilePage";

vi.mock("../api/client", async (orig) => ({ ...(await orig<typeof import("../api/client")>()), getMe: vi.fn(), updateMe: vi.fn() }));
import { ApiError, getMe, updateMe } from "../api/client";

test("reviewer changes their notification email", async () => {
  vi.mocked(getMe).mockResolvedValue({ id: 1, name: "Kim", role: "reviewer", email: "kim@example.com" });
  vi.mocked(updateMe).mockResolvedValue({ id: 1, name: "Kim", role: "reviewer", email: "kim.new@example.com" });
  renderWithProviders(<ProfilePage />);
  const email = await screen.findByLabelText(/notification email/i);
  await userEvent.clear(email);
  await userEvent.type(email, "kim.new@example.com");
  await userEvent.click(screen.getByRole("button", { name: /save/i }));
  expect(updateMe).toHaveBeenCalledWith({ name: "Kim", email: "kim.new@example.com" });
});

test("a tech sees no email field and saves only their name", async () => {
  vi.mocked(getMe).mockResolvedValue({ id: 2, name: "Tess", role: "tech", email: null });
  vi.mocked(updateMe).mockResolvedValue({ id: 2, name: "Tess Tech", role: "tech", email: null });
  renderWithProviders(<ProfilePage />);
  const name = await screen.findByLabelText(/^name/i);
  expect(screen.queryByLabelText(/notification email/i)).toBeNull();
  await userEvent.clear(name);
  await userEvent.type(name, "Tess Tech");
  await userEvent.click(screen.getByRole("button", { name: /save/i }));
  // Exactly { name }: an `email: null` here would clear an email the tech never saw.
  expect(updateMe).toHaveBeenCalledWith({ name: "Tess Tech" });
});

test("a rejected save shows why", async () => {
  vi.mocked(getMe).mockResolvedValue({ id: 1, name: "Kim", role: "reviewer", email: "kim@example.com" });
  // FastAPI's 422 body for a bad email: detail is a list of problems.
  vi.mocked(updateMe).mockRejectedValue(new ApiError(422, [
    { loc: ["body", "email"], msg: "value is not a valid email address: An email address must have an @-sign." },
  ]));
  renderWithProviders(<ProfilePage />);
  const email = await screen.findByLabelText(/notification email/i);
  await userEvent.clear(email);
  await userEvent.type(email, "kim");
  await userEvent.click(screen.getByRole("button", { name: /save/i }));
  expect(await screen.findByRole("alert")).toHaveTextContent("An email address must have an @-sign.");
});

test("clearing the email box sends null", async () => {
  vi.mocked(getMe).mockResolvedValue({ id: 1, name: "Kim", role: "reviewer", email: "kim@example.com" });
  vi.mocked(updateMe).mockResolvedValue({ id: 1, name: "Kim", role: "reviewer", email: null });
  renderWithProviders(<ProfilePage />);
  const email = await screen.findByLabelText(/notification email/i);
  await userEvent.clear(email);
  await userEvent.type(email, "   "); // only spaces counts as empty too
  await userEvent.click(screen.getByRole("button", { name: /save/i }));
  // The backend rejects "" as an email; null means "no email".
  expect(updateMe).toHaveBeenCalledWith({ name: "Kim", email: null });
});
