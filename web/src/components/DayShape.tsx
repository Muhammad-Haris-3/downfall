"use client";

/**
 * Weekday and weekend on one pair of axes, in absolute trips.
 *
 * Not normalised to each day's own total: the interesting fact is that the two
 * are different SHAPES, and scaling each to sum to one would hide that weekdays
 * also carry more.
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
  const H = 260;
  const pad = { l: 4, r: 4, t: 12, b: 4 };

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
      <div style={{ display: "flex", gap: 22, marginBottom: 14, fontSize: 12.5, color: "var(--muted)" }}>
        <span><span aria-hidden style={{ display: "inline-block", width: 18, height: 3, background: "var(--accent)", verticalAlign: "middle", marginRight: 7 }} />Weekday — two peaks</span>
        <span><span aria-hidden style={{ display: "inline-block", width: 18, height: 3, background: "var(--dim)", verticalAlign: "middle", marginRight: 7 }} />Weekend — one, mid-afternoon</span>
      </div>

      <div style={{ border: "2px solid var(--line)", background: "var(--raise)", padding: "16px 16px 0" }}>
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: "100%", height: 260, display: "block" }}>
          <polyline points={pts(weekend)} fill="none" stroke="var(--dim)" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" opacity="0.75" />
          <polyline points={pts(weekday)} fill="none" stroke="var(--accent)" strokeWidth="3.5" strokeLinejoin="round" strokeLinecap="round" />
        </svg>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--dim)", padding: "8px 0 12px", borderTop: "1px solid var(--line)", marginTop: 8 }}>
          {["00", "04", "08", "12", "16", "20", "23"].map((h) => <span key={h}>{h}</span>)}
        </div>
      </div>
    </div>
  );
}
