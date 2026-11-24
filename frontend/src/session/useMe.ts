import { useQuery } from "@tanstack/react-query";
import { ApiError, getMe } from "@/api/client";

/**
 * The signed-in user, cached under the query key ["me"].
 * Never retries a 4xx error; other failures may be.
 */
export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => getMe(),
    retry: (failureCount, error) => {
      if (
        failureCount >= 3 ||
        (error instanceof ApiError && error.status >= 400 && error.status < 500)
      )
        return false;
      return true;
    },
  });
}
