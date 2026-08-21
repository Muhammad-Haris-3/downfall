"use client";

type Band = { lo: number | null; hi: number | null; rel: number; hours: number };

/**
 * Ridership against temperature, as bars rather than a fitted line.
 *
 * A smooth curve through eight points would imply a functional form the data
 * does not establish - and would round off the one feature that matters, which
 * is that the relationship stops rising and turns back down above 30 C. Bars
 * make the turn visible instead of averaging it away.
 */
export default function TempCurve({ bands }: { bands: Band[] }) {
  const max = Math.max(...bands.map((b) => b.rel), 1);
  const label = (b: Band) =>
    b.lo === null ? "below 0" : b.hi === null ? "30+" : `${b.lo}–${b.hi}`;

  return (
    <div style={{ display: "grid", gap: 6 }}>
      {bands.map((b, i) => {
        const w = (b.rel / max) * 100;
        const peak = b.rel === Math.max(...bands.map((x) => x.rel));
        return (
          <div key={i} style={{ display: "grid", gridTemplateColumns: "84px 1fr 130px", alignItems: "center", gap: 12 }}>
            <div style={{ fontSize: 13, color: "var(--muted)", fontFamily: "var(--mono)", textAlign: "right" }}>
              {label(b)} °C
            </div>
            <div style={{ background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 4, height: 26, position: "relative" }}>
              <div
                style={{
                  width: `${w}%`, height: "100%", borderRadius: 3,
                  background: peak ? "var(--accent)" : "color-mix(in srgb, var(--accent) 45%, transparent)",
                }}
              />
              {/* 1.0x is the hour's own average - the line the bars are read against */}
              <div style={{ position: "absolute", left: `${(1 / max) * 100}%`, top: -3, bottom: -3, width: 1, background: "var(--dim)" }} />
            </div>
            <div style={{ fontSize: 13, fontFamily: "var(--mono)", color: "var(--muted)" }}>
              {b.rel.toFixed(2)}× · {(b.hours / 1000).toFixed(1)}k hrs
            </div>
          </div>
        );
      })}
      <div style={{ fontSize: 12, color: "var(--dim)", marginTop: 4 }}>
        The vertical line is 1.00× — that hour-of-week&rsquo;s own average.
      </div>
    </div>
  );
}
