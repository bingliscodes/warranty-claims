import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { createSession } from "@/api/client";
import type { Role } from "@/api/types";
import { TestModeBanner } from "@/components/TestModeBanner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";

export default function RolePickerPage() {
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role | null>(null);
  const [email, setEmail] = useState("");
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const start = useMutation({
    // An arrow, not `mutationFn: createSession`: TanStack passes a second argument we don't want.
    mutationFn: (body: Parameters<typeof createSession>[0]) => createSession(body),
    onSuccess: (me) => {
      // The response is the new user, so store it as ["me"]: the next page needn't fetch it.
      queryClient.setQueryData(["me"], me);
      navigate("/", { replace: true });
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!role) return;
    // Design §5: an empty email box sends null (the backend rejects ""). Techs send no email.
    start.mutate(
      role === "reviewer" ? { name, role, email: email.trim() || null } : { name, role },
    );
  }

  const canContinue = name.trim() !== "" && role !== null && !start.isPending;

  return (
    <>
      <TestModeBanner />
      <main className="mx-auto max-w-md p-4">
        <Card>
          <CardHeader>
            <CardTitle>Who are you?</CardTitle>
            <CardDescription>This browser remembers you after this.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="grid gap-5">
              <div className="grid gap-2">
                <Label htmlFor="name">Your name</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  autoComplete="name"
                  maxLength={100}
                />
              </div>
              <div className="grid gap-2">
                <span id="role-label" className="text-sm font-medium">
                  Role
                </span>
                <RadioGroup
                  aria-labelledby="role-label"
                  value={role ?? ""}
                  onValueChange={(value) => setRole(value as Role)}
                >
                  <div className="flex items-center gap-2">
                    <RadioGroupItem value="tech" id="role-tech" />
                    <Label htmlFor="role-tech">Tech</Label>
                  </div>
                  <div className="flex items-center gap-2">
                    <RadioGroupItem value="reviewer" id="role-reviewer" />
                    <Label htmlFor="role-reviewer">Reviewer</Label>
                  </div>
                </RadioGroup>
              </div>
              {role === "reviewer" && (
                <div className="grid gap-2">
                  <Label htmlFor="email">
                    Notification email <span className="text-muted-foreground">(optional)</span>
                  </Label>
                  <Input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete="email"
                  />
                </div>
              )}
              {start.error && (
                <Alert variant="destructive">
                  <AlertDescription>{start.error.message}</AlertDescription>
                </Alert>
              )}
              <Button type="submit" disabled={!canContinue}>
                Continue
              </Button>
            </form>
          </CardContent>
        </Card>
      </main>
    </>
  );
}
