import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/render";
import RolePickerPage from "./RolePickerPage";

vi.mock("../api/client", async (orig) => ({ ...(await orig<typeof import("../api/client")>()), createSession: vi.fn() }));
import { createSession } from "../api/client";

const renderPage = () => renderWithProviders(<RolePickerPage />, { route: "/start", path: "/start" });

test("reviewer gives a notification email", async () => {
  vi.mocked(createSession).mockResolvedValue({ id: 1, name: "Kim", role: "reviewer", email: "kim@example.com" });
  renderPage();
  expect(screen.queryByLabelText(/notification email/i)).toBeNull();
  await userEvent.type(screen.getByLabelText(/your name/i), "Kim");
  await userEvent.click(screen.getByRole("radio", { name: /reviewer/i }));
  await userEvent.type(screen.getByLabelText(/notification email/i), "kim@example.com");
  await userEvent.click(screen.getByRole("button", { name: /continue/i }));
  expect(createSession).toHaveBeenCalledWith({ name: "Kim", role: "reviewer", email: "kim@example.com" });
});

test("name is required", () => {
  renderPage();
  expect(screen.getByRole("button", { name: /continue/i })).toBeDisabled();
});

test("shows the test-mode banner", () => {
  renderPage();
  expect(screen.getByText("Test mode — don't enter real customer data")).toBeInTheDocument();
});
