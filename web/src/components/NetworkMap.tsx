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
 * and NFR-1 puts the whole project on free tiers with no account anywhere. It
 * is also the better picture: 2,391 dots draw the network's own shape, and a
 * street map underneath would invite reading the streets instead of the data.
 *
 * BOTH AXES MUST BE IN THE SAME UNITS.
 * The first version of this file projected y through Mercator - which returns a
 * dimensionless, radian-scale number - while leaving x in raw degrees. The two
 * ranges then differed by a factor of 57, the shared scale took the smaller,
 * and the entire city collapsed into an eighteen-pixel strip along the bottom
 * of the frame. It shipped looking like a smear.
 *
 * Longitude is therefore converted to radians here as well. Mercator at all,
 * rather than plain lat/lon, because at 40 degrees north the naive projection
 * stretches Manhattan noticeably north-south.
 */
const rad = (deg: number) => (deg * Math.PI) / 180;
const mercatorY = (lat: number) => Math.log(Math.tan(Math.PI / 4 + rad(lat) / 2));

const PAD = 18;

export default function NetworkMap({ stations }: { stations: Station[] }) {
  const [hover, setHover] = useState<Station | null>(null);
  const [onlyTop, setOnlyTop] = useState(false);

  const { points, maxDep, W, H } = useMemo(() => {
    const xs = stations.map((s) => rad(s.lon));
    const ys = stations.map((s) => mercatorY(s.lat));
    const x0 = Math.min(...xs), x1 = Math.max(...xs);
    const y0 = Math.min(...ys), y1 = Math.max(...ys);

    // The frame takes the network's own aspect ratio rather than imposing one,
    // so nothing is stretched to fill a box that was chosen first.
    const spanX = x1 - x0;
    const spanY = y1 - y0;
    const W = 760;
    const H = Math.round(((W - PAD * 2) * spanY) / spanX) + PAD * 2;
    const scale = (W - PAD * 2) / spanX;

    return {
      W,
      H,
      points: stations.map((st) => ({
        st,
        x: PAD + (rad(st.lon) - x0) * scale,
        y: PAD + (y1 - mercatorY(st.lat)) * scale,
      })),
      maxDep: Math.max(...stations.map((d) => d.dep)),
    };
  }, [stations]);

  // Area, not radius, scales with volume - a radius-linear encoding overstates
  // the busiest stations by the square of their lead.
  const radius = (dep: number) => 1.1 + 4.4 * Math.sqrt(dep / maxDep);

  const shown = onlyTop ? points.filter((p) => p.st.top200) : points;
  const rest = shown.filter((p) => !p.st.top200);
  const busiest = shown.filter((p) => p.st.top200);

  return (
    <div>
      <div style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 10, flexWrap: "wrap" }}>
        <label style={{ fontSize: 14, color: "var(--muted)", cursor: "pointer", userSelect: "none" }}>
          <input
            type="checkbox"
            checked={onlyTop}
            onChange={(e) => setOnlyTop(e.target.checked)}
            style={{ marginRight: 8, verticalAlign: "middle" }}
          />
          Show only the 200 busiest
        </label>
        <span style={{ fontSize: 13, color: "var(--dim)", marginLeft: "auto" }}>
          {shown.length.toLocaleString()} stations · dot area ∝ departures recorded
        </span>
      </div>

      <div
        style={{
          position: "relative",
          background: "var(--panel)",
          border: "1px solid var(--line)",
          borderRadius: 10,
          overflow: "hidden",
        }}
      >
        {/* The network is half again as tall as it is wide - it runs from the
            Bronx to Brooklyn - so the frame is given a height and allowed to
            letterbox rather than being stretched to fill a wide box. */}
        <svg
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="xMidYMid meet"
          style={{ width: "100%", height: "min(78vh, 900px)", display: "block" }}
        >
          {/* The bulk of the network first, faintly. At this density the overlap
              is the information: where dots merge, stations are packed. */}
          {rest.map(({ st, x, y }) => (
            <circle
              key={st.s}
              cx={x} cy={y} r={radius(st.dep)}
              fill="var(--muted)" fillOpacity={0.28}
              onMouseEnter={() => setHover(st)}
              onMouseLeave={() => setHover(null)}
              style={{ cursor: "pointer" }}
            />
          ))}
          {/* The cohort on top, so it is never buried by the stations it outranks. */}
          {busiest.map(({ st, x, y }) => (
            <circle
              key={st.s}
              cx={x} cy={y} r={radius(st.dep)}
              fill="var(--accent)" fillOpacity={0.85}
              onMouseEnter={() => setHover(st)}
              onMouseLeave={() => setHover(null)}
              style={{ cursor: "pointer" }}
            />
          ))}
          {hover && (
            <circle
              cx={points.find((p) => p.st.s === hover.s)!.x}
              cy={points.find((p) => p.st.s === hover.s)!.y}
              r={radius(hover.dep) + 4}
              fill="none" stroke="var(--ink)" strokeWidth={1.5}
              pointerEvents="none"
            />
          )}
        </svg>

        <div
          style={{
            position: "absolute", left: 12, bottom: 12,
            background: "color-mix(in srgb, var(--bg) 88%, transparent)",
            border: "1px solid var(--line)", borderRadius: 8,
            padding: "9px 13px", maxWidth: 320, pointerEvents: "none",
            backdropFilter: "blur(6px)",
            opacity: hover ? 1 : 0, transition: "opacity .12s",
          }}
        >
          <div style={{ fontWeight: 650, fontSize: 14 }}>{hover?.n ?? "—"}</div>
          <div style={{ fontSize: 12.5, color: "var(--muted)", fontFamily: "var(--mono)" }}>
            {hover ? `${hover.dep.toLocaleString()} departures · rank ${hover.rank}` : ""}
            {hover?.cap ? ` · ${hover.cap} docks` : ""}
          </div>
        </div>

        <div
          style={{
            position: "absolute", right: 12, top: 12, display: "flex", gap: 14,
            fontSize: 12, color: "var(--muted)",
            background: "color-mix(in srgb, var(--bg) 88%, transparent)",
            border: "1px solid var(--line)", borderRadius: 8, padding: "6px 11px",
            backdropFilter: "blur(6px)",
          }}
        >
          <span>
            <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 4, background: "var(--accent)", marginRight: 6 }} />
            200 busiest
          </span>
          <span>
            <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 4, background: "var(--muted)", opacity: 0.5, marginRight: 6 }} />
            the rest
          </span>
        </div>
      </div>
    </div>
  );
}
