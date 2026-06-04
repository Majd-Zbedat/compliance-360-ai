"use client";

import { AlertTriangle, Clock, Globe, Shield } from "lucide-react";
import { SummaryCard } from "./SummaryCard";

function formatDelta(n: number, unit: string, positiveIsGood: boolean) {
  if (n === 0) return { label: `No change ${unit}`, positive: true };
  const sign = n > 0 ? "+" : "";
  return {
    label: `${sign}${n} ${unit}`,
    positive: positiveIsGood ? n >= 0 : n <= 0,
  };
}

export function DashboardKpis({
  regCount,
  regulationsUploaded,
  highRisk,
  highRiskDelta,
  complianceScore,
  complianceScoreDelta,
  pending,
  pendingLast7d,
}: {
  regCount: number;
  regulationsUploaded: number;
  highRisk: number;
  highRiskDelta: number;
  complianceScore: number;
  complianceScoreDelta: number;
  pending: number;
  pendingLast7d: number;
}) {
  const regTrend =
    regulationsUploaded > 0
      ? { dir: "up" as const, label: `${regulationsUploaded} uploaded`, positive: true }
      : undefined;

  const highTrend = formatDelta(highRiskDelta, "since last week", false);
  const scoreTrend = formatDelta(complianceScoreDelta, "pts vs prior 30d", true);
  const pendingTrend =
    pendingLast7d > 0
      ? { dir: "up" as const, label: `${pendingLast7d} new this week`, positive: false }
      : undefined;

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <SummaryCard
        title="Total Regulations Tracked"
        value={regCount.toLocaleString()}
        sub="Across all jurisdictions"
        Icon={Globe}
        trend={regTrend}
      />
      <SummaryCard
        title="High Risk Issues"
        value={highRisk}
        sub="Require immediate attention"
        Icon={AlertTriangle}
        trend={{
          dir: highRiskDelta <= 0 ? "down" : "up",
          label: highTrend.label,
          positive: highTrend.positive,
        }}
      />
      <SummaryCard
        title="Compliance Score"
        sub={
          complianceScoreDelta === 0
            ? "Based on audit outcomes"
            : `${scoreTrend.label.startsWith("+") ? "↑" : scoreTrend.label.startsWith("-") ? "↓" : ""} ${scoreTrend.label}`
        }
        Icon={Shield}
        gauge={complianceScore}
      />
      <SummaryCard
        title="Pending Reviews"
        value={pending}
        sub="Awaiting analyst sign-off"
        Icon={Clock}
        trend={pendingTrend}
      />
    </div>
  );
}
