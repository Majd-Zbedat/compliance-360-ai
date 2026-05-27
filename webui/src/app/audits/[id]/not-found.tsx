import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function AuditNotFound() {
  return (
    <div className="container max-w-xl space-y-4 py-20 text-center">
      <h1 className="text-2xl font-semibold">Audit not found</h1>
      <p className="text-sm text-muted-foreground">
        The audit you are looking for has not been created or the orchestrator
        is unreachable.
      </p>
      <Button asChild>
        <Link href="/audits">Back to audits</Link>
      </Button>
    </div>
  );
}
