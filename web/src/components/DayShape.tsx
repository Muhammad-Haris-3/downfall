"use client";

/**
 * Weekday and weekend on one pair of axes, normalised to nothing.
 *
 * Plotted in absolute trips rather than as a share of each day's own total,
 * because the interesting fact is that the two are different SHAPES, and
 * normalising each to sum to one would hide that weekdays also carry more.
 */
export default function DayShape({
  weekday,
  weekend,
}: {
  weekday: number[];
  weekend: number[];
}) {
  const max = Math.max(...weekday, ...weekend, 1);
  const W = 720;
  const H = 220;
  const pad = { l: 8, r: 8, t: 10, b: 22 };

  const pts = (series: number[]) =>
    series
      .map((v, h) => {
        const x = pad.l + (h / 23) * (W - pad.l - pad.r);
        const y = H - pad.b - (v / max) * (H - pad.t - pad.b);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto" }}>
        {[0, 6, 12, 18, 23].map((h) => {
          const x = pad.l + (h / 23) * (W - pad.l - pad.r);
          return (
            <g key={h}>
              <line x1={x} x2={x} y1={pad.t} y2={H - pad.b} stroke="var(--line)" />
              <text x={x} y={H - 6} fontSize="11" fill="var(--dim)" textAnchor="middle">
                {String(h).padStart(2, "0")}:00
              </text>
            </g>
          );
        })}
        <polyline points={pts(weekday)} fill="none" stroke="var(--accent)" strokeWidth="2.5" />
        <polyline points={pts(weekend)} fill="none" stroke="var(--warn)" strokeWidth="2.5" strokeDasharray="5 4" />
      </svg>
      <div style={{ display: "flex", gap: 20, fontSize: 13, color: "var(--muted)" }}>
        <span><span style={{ display: "inline-block", width: 18, height: 2, background: "var(--accent)", verticalAlign: "middle", marginRight: 6 }} />Weekday — two peaks</span>
        <span><span style={{ display: "inline-block", width: 18, height: 2, background: "var(--warn)", verticalAlign: "middle", marginRight: 6 }} />Weekend — one, mid-afternoon</span>
      </div>
    </div>
  );
}
