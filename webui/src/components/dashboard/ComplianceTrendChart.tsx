/** Lightweight SVG area chart — data from /audits/stats monthly_compliance. */

export function ComplianceTrendChart({
  data,
}: {
  data: { month: string; score: number }[];
}) {
  const w = 520;
  const h = 188;
  const pad = { t: 8, r: 8, b: 24, l: 8 };
  const innerW = w - pad.l - pad.r;
  const innerH = h - pad.t - pad.b;
  const min = 40;
  const max = 100;

  const points = data.map((d, i) => {
    const x = pad.l + (i / Math.max(data.length - 1, 1)) * innerW;
    const y = pad.t + innerH - ((d.score - min) / (max - min)) * innerH;
    return { x, y, v: d.score, month: d.month };
  });

  const line = points.map((p) => `${p.x},${p.y}`).join(" ");
  const area = `${pad.l},${pad.t + innerH} ${line} ${pad.l + innerW},${pad.t + innerH}`;

  return (
    <div className="rounded-lg border border-border bg-card p-6 shadow-card lg:col-span-2">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-primary">Compliance Trend</p>
          <p className="mt-0.5 text-xs text-[#9CA3AF]">Average audit score by month (from your audits)</p>
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
            key={`${p.month}-${i}`}
            x={p.x}
            y={h - 4}
            textAnchor="middle"
            fontSize={11}
            fill="#9CA3AF"
          >
            {p.month}
          </text>
        ))}
      </svg>
    </div>
  );
}
