import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Me } from "@/api/types";
import { useMe } from "@/session/useMe";
import { updateMe } from "@/api/client";
/**
 * "Name" and, for reviewers only, "Notification email", plus a "Save" button.
 * Saving calls updateMe and stores the answer as ["me"]. Design §5: an empty email box sends null,
 * and a tech's profile sends only the name. A rejected save shows a red Alert above the button.
 */
export default function ProfilePage() {
  const { data: me } = useMe();
  if (!me) return null;
  return <ProfileForm me={me} />;
}

function ProfileForm({ me }: { me: Me }) {
  const [name, setName] = useState(me.name);
  const [email, setEmail] = useState(me.email);
  const showEmail = me.role === "reviewer";
  const queryClient = useQueryClient();
  const save = useMutation({
    mutationFn: (body: { name: string; email?: string | null }) =>
      updateMe(body),
    onSuccess: (updated) => queryClient.setQueryData(["me"], updated), // the nav bar sees the new name
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();

    save.mutate(showEmail ? { name, email: email?.trim() || null } : { name });
  }

  return (
    <form onSubmit={handleSubmit} className="grid max-w-md gap-2">
      <Label htmlFor="name">Name </Label>
      <Input id="name" value={name} onChange={(e) => setName(e.target.value)} />
      {showEmail && (
        <>
          <Label htmlFor="email">Notification email</Label>
          <Input
            id="email"
            value={email ?? ""}
            onChange={(e) => setEmail(e.target.value)}
          />
        </>
      )}
      {save.error && (
        <Alert variant="destructive">
          <AlertDescription>{save.error.message}</AlertDescription>
        </Alert>
      )}
      <Button type="submit" disabled={save.isPending}>
        Save
      </Button>
    </form>
  );
}
