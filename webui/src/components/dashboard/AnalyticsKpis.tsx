"use client";

import { AlertTriangle, Clock, Shield, TrendingUp } from "lucide-react";
import { SummaryCard } from "./SummaryCard";

export function AnalyticsKpis({
  criticalGaps,
  breached,
}: {
  criticalGaps: number;
  breached: number;
}) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <SummaryCard
        title="Avg Compliance Score"
        value="87%"
        sub="Across all departments"
        Icon={Shield}
        trend={{ dir: "up", label: "+4.2%", positive: true }}
      />
      <SummaryCard
        title="Critical Risk Gaps"
        value={criticalGaps}
        sub="Requiring remediation"
        Icon={AlertTriangle}
        trend={{ dir: "down", label: "-3 this quarter", positive: true }}
      />
      <SummaryCard
        title="Regulations Breached"
        value={breached}
        sub="Active non-compliance"
        Icon={TrendingUp}
        trend={{ dir: "up", label: "+1 this month", positive: false }}
      />
      <SummaryCard
        title="Avg Time to Resolve"
        value="4.8 days"
        sub="Mean remediation time"
        Icon={Clock}
        trend={{ dir: "down", label: "-0.9 days", positive: true }}
      />
    </div>
  );
}
