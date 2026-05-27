import { Card, CardContent } from "@/components/ui/card";
import { DocumentsTable } from "@/components/DocumentsTable";
import { api, type AuditSummary } from "@/lib/api";

export const dynamic = "force-dynamic";

async function safeAudits(): Promise<AuditSummary[]> {
  try {
    return await api.listAudits();
  } catch {
    return [];
  }
}

export default async function AuditsPage() {
  const audits = await safeAudits();

  return (
    <div className="mx-auto max-w-[1200px] space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-primary">Document Management</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Upload, track, and review AI-analyzed compliance documents.
        </p>
      </div>

      {audits.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center text-sm text-muted-foreground">
            No documents yet — upload a contract from the dashboard or use Upload Document above.
          </CardContent>
        </Card>
      ) : (
        <DocumentsTable audits={audits} />
      )}
    </div>
  );
}
