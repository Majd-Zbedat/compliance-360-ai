"use client";

import { AlertTriangle, Clock, Globe, Shield } from "lucide-react";
import { SummaryCard } from "./SummaryCard";

export function DashboardKpis({
  regCount,
  highRisk,
  complianceScore,
  pending,
}: {
  regCount: number;
  highRisk: number;
  complianceScore: number;
  pending: number;
}) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <SummaryCard
        title="Total Regulations Tracked"
        value={regCount.toLocaleString()}
        sub="Across all jurisdictions"
        Icon={Globe}
        trend={{ dir: "up", label: "+23 this month", positive: true }}
      />
      <SummaryCard
        title="High Risk Issues"
        value={highRisk}
        sub="Require immediate attention"
        Icon={AlertTriangle}
        trend={{ dir: "up", label: "+5 since last week", positive: false }}
      />
      <SummaryCard
        title="Compliance Score"
        sub="↑ 4pts from last quarter"
        Icon={Shield}
        gauge={complianceScore}
      />
      <SummaryCard
        title="Pending Reviews"
        value={pending || 132}
        sub="Awaiting analyst sign-off"
        Icon={Clock}
        trend={{ dir: "down", label: "-11 this week", positive: true }}
      />
    </div>
  );
}
