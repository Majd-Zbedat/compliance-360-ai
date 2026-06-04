import { AlertTriangle, CheckCircle2, Clock, ShieldAlert } from "lucide-react";
import type { AuditSummary } from "@/lib/api";

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const diffMs = Date.now() - then;
  const mins = Math.floor(diffMs / 60000);
  if (mins < 60) return `${Math.max(1, mins)}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days} days ago`;
  return new Date(iso).toLocaleDateString();
}

function alertFromAudit(a: AuditSummary) {
  if (a.status === "Review") {
    return {
      Icon: Clock,
      icolor: "#F59E0B",
      ibg: "#FFF7ED",
      text: `${a.filename} flagged for human review`,
      time: relativeTime(a.created_at),
    };
  }
  if (a.status === "Rejected") {
    return {
      Icon: ShieldAlert,
      icolor: "#EF4444",
      ibg: "#FEF2F2",
      text: `${a.filename} rejected by guardrail`,
      time: relativeTime(a.created_at),
    };
  }
  if (a.overall_risk === "High" || a.high_count > 0) {
    return {
      Icon: AlertTriangle,
      icolor: "#EF4444",
      ibg: "#FEF2F2",
      text: `${a.filename} — ${a.high_count} high-risk finding${a.high_count !== 1 ? "s" : ""}`,
      time: relativeTime(a.created_at),
    };
  }
  return {
    Icon: CheckCircle2,
    icolor: "#86BC25",
    ibg: "#F0F9E8",
    text: `${a.filename} audit completed (${a.overall_risk} risk)`,
    time: relativeTime(a.created_at),
  };
}

export function RecentAlerts({ audits }: { audits: AuditSummary[] }) {
  const alerts = audits.slice(0, 5).map(alertFromAudit);
  const active = audits.filter(
    (a) => a.status === "Review" || a.overall_risk === "High" || a.high_count > 0,
  ).length;

  if (alerts.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card p-5 shadow-card">
        <p className="text-sm font-semibold text-primary">Recent Alerts</p>
        <p className="mt-3 text-xs text-muted-foreground">No audits yet — upload a contract to get started.</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-card p-5 shadow-card">
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm font-semibold text-primary">Recent Alerts</p>
        {active > 0 && (
          <span
            className="rounded-full px-2 py-0.5 text-xs font-medium"
            style={{ backgroundColor: "#FEF2F2", color: "#991B1B" }}
          >
            {active} active
          </span>
        )}
      </div>
      <div className="space-y-3">
        {alerts.map((a, i) => (
          <div key={i} className="flex items-start gap-3">
            <div
              className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md"
              style={{ backgroundColor: a.ibg }}
            >
              <a.Icon size={13} style={{ color: a.icolor }} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs leading-snug text-[#374151]">{a.text}</p>
              <p className="mt-0.5 text-xs text-[#9CA3AF]">{a.time}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
