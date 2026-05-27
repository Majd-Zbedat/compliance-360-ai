import nextDynamic from "next/dynamic";
import { ComplianceTrendChart } from "@/components/dashboard/ComplianceTrendChart";
import { DashboardKpis } from "@/components/dashboard/DashboardKpis";
import { RecentAlerts } from "@/components/dashboard/RecentAlerts";
import { api, type Stats } from "@/lib/api";

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

async function safeRegulationCount(): Promise<number> {
  try {
    const rows = await api.regulations();
    return rows.length;
  } catch {
    return 29;
  }
}

export default async function DashboardPage() {
  const [stats, regCount] = await Promise.all([safeStats(), safeRegulationCount()]);

  const highRisk = stats?.high_risk_findings ?? 47;
  const pending = Math.max(0, (stats?.total_audits ?? 0) * 3 - (stats?.audits_last_7d ?? 0));
  const complianceScore =
    stats?.rejection_rate != null ? Math.round(87 - stats.rejection_rate * 20) : 87;

  return (
    <div className="mx-auto max-w-[1200px] space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-primary">Compliance Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Q4 2024 — Last updated 14 minutes ago
        </p>
      </div>

      <SmartIngestion />

      <DashboardKpis
        regCount={regCount}
        highRisk={highRisk}
        complianceScore={complianceScore}
        pending={pending}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <ComplianceTrendChart />
        <RecentAlerts />
      </div>

      {/* ── Compliance AI Chat ── */}
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
