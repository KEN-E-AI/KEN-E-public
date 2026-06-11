import type { PropsWithChildren, ReactElement } from "react";
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

/**
 * Render a component under a fresh, isolated QueryClient.
 *
 * Components that call `useQueryClient` / `useQuery` (e.g. ChatInterface, which
 * caches conversation history) require a provider in the tree. A new client per
 * call keeps each test's cache isolated — no stale-while-revalidate bleed across
 * tests in the same file.
 *
 * The provider is supplied via RTL's `wrapper` option (not inline) so that the
 * returned `rerender` re-applies it — bare-element rerenders would otherwise
 * lose the provider and throw "No QueryClient set".
 */
export function renderWithQueryClient(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: 0 },
    },
  });
  return render(ui, {
    wrapper: ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    ),
  });
}
