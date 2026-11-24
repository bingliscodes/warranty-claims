import type { ReactNode } from "react";
import { Navigate } from "react-router";

import { useMe } from "@/session/useMe";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/api/client";

/**
 * Shows `children` when signed in.
 * - While the user is loading: nothing.
 * - A 401: <Navigate to="/start" replace />.
 * - Any other failure: "Can't reach the server" with a Retry button (design §6).
 */
export default function RequireUser({ children }: { children: ReactNode }) {
  const me = useMe();

  if (me.isPending) return null;

  if (me.error instanceof ApiError && me.error.status === 401) {
    return <Navigate to="/start" replace />;
  }
  if (me.error) {
    return (
      <>
        <p>Can't reach the server</p>
        <Button onClick={() => me.refetch()}>Retry</Button>
      </>
    );
  }

  return children;
}
