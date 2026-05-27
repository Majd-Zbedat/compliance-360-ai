import { AlertTriangle, CheckCircle2, Clock } from "lucide-react";

const alerts = [
  {
    Icon: AlertTriangle,
    icolor: "#EF4444",
    ibg: "#FEF2F2",
    text: "GDPR Article 17 deadline in 3 days",
    time: "2h ago",
  },
  {
    Icon: Clock,
    icolor: "#F59E0B",
    ibg: "#FFF7ED",
    text: "SOX Section 404 review is overdue",
    time: "5h ago",
  },
  {
    Icon: CheckCircle2,
    icolor: "#86BC25",
    ibg: "#F0F9E8",
    text: "CCPA compliance audit completed",
    time: "Yesterday",
  },
  {
    Icon: AlertTriangle,
    icolor: "#F59E0B",
    ibg: "#FFF7ED",
    text: "New FCA regulation requires attention",
    time: "2 days ago",
  },
];

export function RecentAlerts() {
  return (
    <div className="rounded-lg border border-border bg-card p-5 shadow-card">
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm font-semibold text-primary">Recent Alerts</p>
        <span
          className="rounded-full px-2 py-0.5 text-xs font-medium"
          style={{ backgroundColor: "#FEF2F2", color: "#991B1B" }}
        >
          5 active
        </span>
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
