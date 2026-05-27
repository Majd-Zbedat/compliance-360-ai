import { AnalyticsKpis } from "@/components/dashboard/AnalyticsKpis";
import { api, type Stats } from "@/lib/api";

export const dynamic = "force-dynamic";

async function safeStats(): Promise<Stats | null> {
  try {
    return await api.stats();
  } catch {
    return null;
  }
}

const heatmap = {
  departments: ["Finance", "Legal", "HR", "IT", "Operations"],
  categories: ["Data Privacy", "Contract Risk", "Regulatory", "Financial", "Operational"],
  cells: [
    ["critical", "high", "medium", "low", "medium"],
    ["high", "medium", "low", "medium", "high"],
    ["medium", "low", "medium", "high", "low"],
    ["low", "medium", "high", "critical", "medium"],
    ["medium", "high", "low", "medium", "low"],
  ] as const,
};

const levelStyle: Record<string, { bg: string; text: string; label: string }> = {
  low: { bg: "#F0F9E8", text: "#2D6A0A", label: "Low" },
  medium: { bg: "#FEF9C3", text: "#854D0E", label: "Medium" },
  high: { bg: "#FFEDD5", text: "#9A3412", label: "High" },
  critical: { bg: "#FEE2E2", text: "#991B1B", label: "Critical" },
};

const chartLines = [
  { label: "Overall", color: "#86BC25" },
  { label: "Financial", color: "#3B82F6" },
  { label: "Data Privacy", color: "#8B5CF6" },
  { label: "Operational", color: "#F59E0B" },
];

export default async function AnalyticsPage() {
  const stats = await safeStats();
  const breached = stats?.high_risk_findings ? Math.min(9, Math.ceil(stats.high_risk_findings / 5)) : 3;

  return (
    <div className="mx-auto max-w-[1200px] space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-primary">Analytics & Risk Intelligence</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Compliance trend analysis and departmental risk assessment — FY 2024
        </p>
      </div>

      <AnalyticsKpis
        criticalGaps={stats?.high_risk_findings ?? 14}
        breached={breached}
      />

      <div className="rounded-lg border border-border bg-card p-6 shadow-card">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-primary">Compliance Score Trends by Category</p>
            <p className="text-xs text-muted-foreground">Jan – Dec 2024</p>
          </div>
          <div className="flex flex-wrap gap-3">
            {chartLines.map((l) => (
              <span key={l.label} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: l.color }} />
                {l.label}
              </span>
            ))}
          </div>
        </div>
        <CategoryTrendChart />
      </div>

      <div className="rounded-lg border border-border bg-card p-6 shadow-card">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm font-semibold text-primary">Risk Gap Heatmap — by Department</p>
          <div className="flex gap-2">
            {(["low", "medium", "high", "critical"] as const).map((k) => (
              <span
                key={k}
                className="rounded px-2 py-0.5 text-[10px] font-medium"
                style={{ backgroundColor: levelStyle[k].bg, color: levelStyle[k].text }}
              >
                {levelStyle[k].label}
              </span>
            ))}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-sm">
            <thead>
              <tr>
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground" />
                {heatmap.categories.map((c) => (
                  <th
                    key={c}
                    className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                  >
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {heatmap.departments.map((dept, ri) => (
                <tr key={dept}>
                  <td className="px-3 py-2 text-sm font-medium text-brand-ink">{dept}</td>
                  {heatmap.cells[ri].map((level, ci) => (
                    <td key={ci} className="p-1.5">
                      <div
                        className="rounded-md px-3 py-4 text-center text-xs font-semibold"
                        style={{
                          backgroundColor: levelStyle[level].bg,
                          color: levelStyle[level].text,
                        }}
                      >
                        {levelStyle[level].label}
                      </div>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function CategoryTrendChart() {
  const w = 900;
  const h = 220;
  const pad = { t: 12, r: 12, b: 28, l: 36 };
  const innerW = w - pad.l - pad.r;
  const innerH = h - pad.t - pad.b;
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const data = [72, 74, 73, 76, 78, 77, 80, 82, 81, 84, 86, 88];

  const points = data.map((v, i) => ({
    x: pad.l + (i / (data.length - 1)) * innerW,
    y: pad.t + innerH - ((v - 50) / 50) * innerH,
  }));
  const line = points.map((p) => `${p.x},${p.y}`).join(" ");

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" role="img" aria-label="Category compliance trends">
      {[50, 65, 80, 95].map((v, i) => {
        const y = pad.t + innerH - ((v - 50) / 50) * innerH;
        return (
          <g key={v}>
            <line x1={pad.l} x2={w - pad.r} y1={y} y2={y} stroke="#F0F2F5" strokeDasharray="3 3" />
            <text x={pad.l - 8} y={y + 4} textAnchor="end" fontSize={10} fill="#9CA3AF">
              {v}
            </text>
          </g>
        );
      })}
      <polyline points={line} fill="none" stroke="#F59E0B" strokeWidth={2.5} strokeLinejoin="round" />
      {points.map((p, i) => (
        <text key={months[i]} x={p.x} y={h - 6} textAnchor="middle" fontSize={10} fill="#9CA3AF">
          {months[i]}
        </text>
      ))}
    </svg>
  );
}
