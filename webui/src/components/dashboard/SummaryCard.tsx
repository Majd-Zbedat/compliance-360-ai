"use client";

import { LucideIcon, TrendingDown, TrendingUp } from "lucide-react";
import { CircularGauge } from "./CircularGauge";

export function SummaryCard({
  title,
  value,
  sub,
  Icon,
  trend,
  gauge,
}: {
  title: string;
  value?: string | number;
  sub: string;
  Icon: LucideIcon;
  trend?: { dir: "up" | "down"; label: string; positive: boolean };
  gauge?: number;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-5 shadow-card">
      <div className="mb-4 flex items-start justify-between">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-secondary">
          <Icon size={16} className="text-primary" />
        </div>
        {trend && (
          <span
            className="flex items-center gap-0.5 text-xs font-medium"
            style={{ color: trend.positive ? "#2D6A0A" : "#991B1B" }}
          >
            {trend.dir === "up" ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
            {trend.label}
          </span>
        )}
      </div>
      {gauge !== undefined ? (
        <div className="flex items-center gap-4">
          <CircularGauge value={gauge} />
          <div>
            <p className="mb-1 text-xs font-medium text-[#9CA3AF]">{title}</p>
            <p className="text-xs text-muted-foreground">{sub}</p>
          </div>
        </div>
      ) : (
        <>
          <p className="mb-0.5 text-2xl font-bold text-primary">{value}</p>
          <p className="mb-1 text-xs font-medium text-[#9CA3AF]">{title}</p>
          <p className="text-xs text-muted-foreground">{sub}</p>
        </>
      )}
    </div>
  );
}
