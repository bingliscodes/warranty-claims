import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router";
import { ThemeProvider } from "../theme/ThemeProvider";

/**
 * Renders `ui` the way main.tsx does, but with a fresh query cache and an in-memory router.
 * `route` is the starting URL. With `path`, `ui` renders at that route, so useParams works.
 */
export function renderWithProviders(
  ui: ReactElement,
  opts: { route?: string; path?: string } = {},
) {
  const queryClient = new QueryClient({
    // retryDelay 0: a hook with its own retry rule (useMe) retries at once instead of waiting 1s, 2s, 4s.
    defaultOptions: { queries: { retry: false, retryDelay: 0 }, mutations: { retry: false } },
  });
  const result = render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <MemoryRouter initialEntries={[opts.route ?? "/"]}>
          {opts.path ? (
            <Routes>
              <Route path={opts.path} element={ui} />
            </Routes>
          ) : (
            ui
          )}
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  );
  return { ...result, queryClient };
}
