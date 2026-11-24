import { TriangleAlert } from "lucide-react";
import { Alert, AlertTitle } from "@/components/ui/alert";

export function TestModeBanner() {
  return (
    <Alert className="rounded-none border-x-0 border-t-0">
      <TriangleAlert />
      <AlertTitle>{"Test mode — don't enter real customer data"}</AlertTitle>
    </Alert>
  );
}
