import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router";
import { endSession } from "@/api/client";
import { TestModeBanner } from "@/components/TestModeBanner";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button, buttonVariants } from "@/components/ui/button";
import { useMe } from "@/session/useMe";

export function NavBar() {
  const { data: me } = useMe();
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  // Design §6: end the session, forget the cached user (so the old name can't flash), then pick again.
  // onSettled, not onSuccess: even if the DELETE fails, picking a role gives the browser a new cookie.
  const switchRole = useMutation({
    mutationFn: () => endSession(),
    onSettled: () => {
      queryClient.clear();
      navigate("/start", { replace: true });
    },
  });

  return (
    <header className="border-b">
      <TestModeBanner />
      <nav className="mx-auto flex max-w-5xl items-center gap-2 px-4 py-2">
        {/* Links styled as buttons: Base UI's Button would add role="button" to them. */}
        <Link to="/" className={buttonVariants({ variant: "ghost" })}>
          Claims
        </Link>
        <div className="ml-auto flex items-center gap-1">
          <span className="px-2 text-sm text-muted-foreground">{me?.name}</span>
          <Link to="/profile" className={buttonVariants({ variant: "ghost" })}>
            Profile
          </Link>
          <ThemeToggle />
          <Button
            variant="outline"
            onClick={() => switchRole.mutate()}
            disabled={switchRole.isPending}
          >
            Switch role
          </Button>
        </div>
      </nav>
    </header>
  );
}
