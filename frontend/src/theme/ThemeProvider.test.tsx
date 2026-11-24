import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeToggle } from "../components/ThemeToggle";
import { renderWithProviders } from "../test/render";

test("dark theme is applied and remembered", async () => {
  renderWithProviders(<ThemeToggle />);
  await userEvent.click(screen.getByRole("button", { name: /theme/i }));
  await userEvent.click(await screen.findByRole("menuitem", { name: /dark/i }));
  expect(document.documentElement).toHaveClass("dark");
  expect(localStorage.getItem("warranty.theme")).toBe("dark");
});

test("system theme follows the device", () => {
  vi.spyOn(window, "matchMedia").mockReturnValue({ matches: true, addEventListener() {}, removeEventListener() {} } as unknown as MediaQueryList);
  renderWithProviders(<ThemeToggle />);
  expect(document.documentElement).toHaveClass("dark");
});
