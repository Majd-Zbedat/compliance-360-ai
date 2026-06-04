import nextDynamic from "next/dynamic";
import { ComplianceTrendChart } from "@/components/dashboard/ComplianceTrendChart";
import { DashboardKpis } from "@/components/dashboard/DashboardKpis";
import { RecentAlerts } from "@/components/dashboard/RecentAlerts";
import { api, type AuditSummary, type Stats } from "@/lib/api";

const ComplianceChat = nextDynamic(
  () => import("@/components/ComplianceChat").then((m) => m.ComplianceChat),
  { ssr: false, loading: () => <ChatPlaceholder /> },
);

const SmartIngestion = nextDynamic(
  () => import("@/components/SmartIngestion").then((m) => m.SmartIngestion),
  { ssr: false, loading: () => <IngestionPlaceholder /> },
);

export const dynamic = "force-dynamic";

async function safeStats(): Promise<Stats | null> {
  try {
    return await api.stats();
  } catch {
    return null;
  }
}

async function safeAudits(): Promise<AuditSummary[]> {
  try {
    return await api.listAudits();
  } catch {
    return [];
  }
}

function formatLastUpdated(iso?: string | null): string {
  if (!iso) return "No audits yet";
  const then = new Date(iso);
  const diffMs = Date.now() - then.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "Last updated just now";
  if (mins < 60) return `Last updated ${mins} minute${mins !== 1 ? "s" : ""} ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `Last updated ${hrs} hour${hrs !== 1 ? "s" : ""} ago`;
  return `Last updated ${then.toLocaleDateString()}`;
}

export default async function DashboardPage() {
  const [stats, audits] = await Promise.all([safeStats(), safeAudits()]);

  const regCount = stats?.regulation_count ?? 0;
  const highRisk = stats?.high_risk_findings ?? 0;
  const pending = stats?.pending_reviews ?? 0;
  const complianceScore = stats?.compliance_score ?? 0;
  const trendData = stats?.monthly_compliance?.length
    ? stats.monthly_compliance
    : [{ month: "—", score: complianceScore }];

  return (
    <div className="mx-auto max-w-[1200px] space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-primary">Compliance Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {stats?.total_audits ?? 0} audits · {formatLastUpdated(stats?.last_audit_at)}
        </p>
      </div>

      <SmartIngestion />

      <DashboardKpis
        regCount={regCount}
        regulationsUploaded={stats?.regulations_uploaded ?? 0}
        highRisk={highRisk}
        highRiskDelta={stats?.high_risk_delta_7d ?? 0}
        complianceScore={complianceScore}
        complianceScoreDelta={stats?.compliance_score_delta ?? 0}
        pending={pending}
        pendingLast7d={stats?.pending_reviews_last_7d ?? 0}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <ComplianceTrendChart data={trendData} />
        <RecentAlerts audits={audits} />
      </div>

      <div>
        <div className="mb-4 flex items-center gap-2.5">
          <div className="h-5 w-0.5 rounded-full bg-accent" />
          <p className="text-xs font-semibold uppercase tracking-widest text-primary">
            Compliance AI Assistant
          </p>
        </div>
        <ComplianceChat />
      </div>
    </div>
  );
}

function ChatPlaceholder() {
  return (
    <div className="h-[640px] animate-pulse rounded-lg border border-border bg-card" />
  );
}

function IngestionPlaceholder() {
  return (
    <div className="rounded-lg border-2 border-dashed border-border bg-[#FAFAFA] p-10 text-center text-sm text-muted-foreground">
      Loading upload zone…
    </div>
  );
}
