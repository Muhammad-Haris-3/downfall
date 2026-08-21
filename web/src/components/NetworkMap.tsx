"use client";

import { useMemo, useState } from "react";

export type Station = {
  s: string;
  n: string;
  lat: number;
  lon: number;
  cap: number | null;
  dep: number;
  arr: number;
  rank: number;
  top200: boolean;
};

/**
 * Every station at its position, with no basemap underneath.
 *
 * That is a decision, not an omission. Every tile provider wants an API key,
 * and NFR-1 puts the whole project on free tiers with no account anywhere. But
 * it is also the better picture: 2,391 dots draw the network's own shape, and a
 * street map underneath would invite reading the streets instead of the data.
 *
 * Web Mercator, because the alternative at this latitude stretches Manhattan
 * noticeably north-south and the result looks subtly wrong to anyone who knows
 * the city.
 */
function mercator(lat: number) {
  return Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 180 / 2));
}

const W = 900;
const H = 760;
const PAD = 26;

export default function NetworkMap({ stations }: { stations: Station[] }) {
  const [hover, setHover] = useState<Station | null>(null);
  const [onlyTop, setOnlyTop] = useState(false);

  const { points, maxDep } = useMemo(() => {
    const lons = stations.map((s) => s.lon);
    const ys = stations.map((s) => mercator(s.lat));
    const [lo0, lo1] = [Math.min(...lons), Math.max(...lons)];
    const [y0, y1] = [Math.min(...ys), Math.max(...ys)];
    const sx = (W - PAD * 2) / (lo1 - lo0);
    const sy = (H - PAD * 2) / (y1 - y0);
    const s = Math.min(sx, sy);
    const ox = PAD + (W - PAD * 2 - (lo1 - lo0) * s) / 2;
    const oy = PAD + (H - PAD * 2 - (y1 - y0) * s) / 2;

    return {
      points: stations.map((st) => ({
        st,
        x: ox + (st.lon - lo0) * s,
        y: oy + (y1 - mercator(st.lat)) * s,
      })),
      maxDep: Math.max(...stations.map((d) => d.dep)),
    };
  }, [stations]);

  // Area, not radius, scales with volume - a radius-linear encoding overstates
  // the busiest stations by the square of their lead.
  const radius = (dep: number) => 1.4 + 5.6 * Math.sqrt(dep / maxDep);

  const shown = onlyTop ? points.filter((p) => p.st.top200) : points;

  return (
    <div>
      <div style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 12 }}>
        <label style={{ fontSize: 14, color: "var(--muted)", cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={onlyTop}
            onChange={(e) => setOnlyTop(e.target.checked)}
            style={{ marginRight: 8 }}
          />
          Show only the 200 busiest
        </label>
        <span style={{ fontSize: 13, color: "var(--dim)", marginLeft: "auto" }}>
          {shown.length.toLocaleString()} stations · dot area ∝ departures recorded
        </span>
      </div>

      <div style={{ position: "relative", background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 10 }}>
        <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}>
          {shown.map(({ st, x, y }) => (
            <circle
              key={st.s}
              cx={x}
              cy={y}
              r={radius(st.dep)}
              fill={st.top200 ? "var(--accent)" : "var(--muted)"}
              fillOpacity={st.top200 ? 0.75 : 0.4}
              onMouseEnter={() => setHover(st)}
              onMouseLeave={() => setHover(null)}
              style={{ cursor: "pointer" }}
            />
          ))}
        </svg>

        {hover && (
          <div
            style={{
              position: "absolute", left: 14, bottom: 14,
              background: "var(--bg)", border: "1px solid var(--line)",
              borderRadius: 8, padding: "10px 14px", maxWidth: 340, pointerEvents: "none",
            }}
          >
            <div style={{ fontWeight: 650 }}>{hover.n}</div>
            <div style={{ fontSize: 13, color: "var(--muted)", fontFamily: "var(--mono)" }}>
              {hover.dep.toLocaleString()} departures recorded · rank {hover.rank}
              {hover.cap ? ` · ${hover.cap} docks` : ""}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
