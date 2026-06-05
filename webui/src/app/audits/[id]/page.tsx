import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronLeft, ShieldCheck, ShieldX } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, RiskBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";
import { ComplianceReportCard } from "@/components/ComplianceReportCard";
import { ReviewDecisionBar } from "@/components/ReviewDecisionBar";
import { FindingsTable } from "./findings-table";

export const dynamic = "force-dynamic";

export default async function AuditDetailPage({ params }: { params: { id: string } }) {
  let audit;
  try {
    audit = await api.getAudit(params.id);
  } catch {
    notFound();
  }

  return (
    <div className="container max-w-7xl space-y-6 py-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <Button asChild variant="ghost" size="sm" className="-ml-2">
            <Link href="/audits" className="gap-1">
              <ChevronLeft className="h-4 w-4" /> All audits
            </Link>
          </Button>
          <h1 className="text-2xl font-semibold tracking-tight">{audit.filename}</h1>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{audit.id}</code>
            <Badge variant="status">{audit.status}</Badge>
            {audit.status !== "Rejected" && <RiskBadge risk={audit.overall_risk} />}
            <span className="text-muted-foreground">
              Submitted {formatDateTime(audit.created_at)}
            </span>
          </div>
        </div>
        <div className="flex flex-col items-end gap-2 text-sm">
          <GuardrailPill
            kind="input"
            passed={audit.input_guardrail_passed}
            reason={audit.rejection_reason}
          />
          <GuardrailPill kind="output" passed={audit.output_guardrail_passed} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetaCard label="Parties" value={audit.parties.length ? audit.parties.join(", ") : "—"} />
        <MetaCard label="Jurisdiction" value={audit.jurisdiction || "—"} />
        <MetaCard label="Contract type" value={audit.contract_type || "—"} />
        <MetaCard label="Requester" value={audit.requester || "—"} />
      </div>

      <ReviewDecisionBar auditId={audit.id} initialStatus={audit.review_status} />

      <ComplianceReportCard audit={audit} />

      {audit.status !== "Rejected" && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>
                Findings ({audit.findings.filter((f) => f.risk === "High" || f.risk === "Medium").length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              <FindingsTable findings={audit.findings} clauses={audit.clauses} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Audit report (guardrail-validated)</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="whitespace-pre-wrap rounded-lg border border-border bg-muted/30 p-4 text-sm leading-relaxed">
                {audit.safe_report_markdown || audit.report_markdown || "No report generated."}
              </pre>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

function MetaCard({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="space-y-1 p-4">
        <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
        <div className="truncate text-sm font-medium">{value}</div>
      </CardContent>
    </Card>
  );
}

function GuardrailPill({
  kind,
  passed,
  reason,
}: {
  kind: "input" | "output";
  passed: boolean;
  reason?: string | null;
}) {
  const Icon = passed ? ShieldCheck : ShieldX;
  return (
    <div
      className={
        "flex items-center gap-2 rounded-md border px-2.5 py-1 text-xs " +
        (passed
          ? "border-risk-low/40 text-risk-low"
          : "border-risk-high/40 text-risk-high")
      }
      title={reason || undefined}
    >
      <Icon className="h-3.5 w-3.5" />
      <span className="font-medium">
        {kind === "input" ? "Input guardrail" : "Output guardrail"}:{" "}
        {passed ? "passed" : "failed"}
      </span>
    </div>
  );
}
