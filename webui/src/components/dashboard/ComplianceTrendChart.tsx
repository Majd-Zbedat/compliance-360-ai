/** Lightweight SVG area chart matching Figma dashboard trend widget (no recharts dep). */

const data = [61, 65, 63, 68, 72, 70, 75, 78, 76, 82, 85, 87];
const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function ComplianceTrendChart() {
  const w = 520;
  const h = 188;
  const pad = { t: 8, r: 8, b: 24, l: 8 };
  const innerW = w - pad.l - pad.r;
  const innerH = h - pad.t - pad.b;
  const min = 50;
  const max = 100;

  const points = data.map((v, i) => {
    const x = pad.l + (i / (data.length - 1)) * innerW;
    const y = pad.t + innerH - ((v - min) / (max - min)) * innerH;
    return { x, y, v };
  });

  const line = points.map((p) => `${p.x},${p.y}`).join(" ");
  const area = `${pad.l},${pad.t + innerH} ${line} ${pad.l + innerW},${pad.t + innerH}`;

  return (
    <div className="rounded-lg border border-border bg-card p-6 shadow-card lg:col-span-2">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-primary">Compliance Trend — FY 2024</p>
          <p className="mt-0.5 text-xs text-[#9CA3AF]">Overall compliance score by month</p>
        </div>
        <span className="rounded bg-secondary px-2.5 py-1 text-xs text-primary">Monthly</span>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" role="img" aria-label="Compliance trend chart">
        {[0, 1, 2, 3].map((i) => (
          <line
            key={i}
            x1={pad.l}
            x2={w - pad.r}
            y1={pad.t + (innerH / 3) * i}
            y2={pad.t + (innerH / 3) * i}
            stroke="#F0F2F5"
            strokeDasharray="3 3"
          />
        ))}
        <polygon points={area} fill="rgba(134,188,37,0.2)" />
        <polyline
          points={line}
          fill="none"
          stroke="#86BC25"
          strokeWidth={2.5}
          strokeLinejoin="round"
        />
        {points.map((p, i) => (
          <text
            key={months[i]}
            x={p.x}
            y={h - 4}
            textAnchor="middle"
            fontSize={11}
            fill="#9CA3AF"
          >
            {months[i]}
          </text>
        ))}
      </svg>
    </div>
  );
}
