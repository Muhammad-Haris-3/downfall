"use client";

import { useState } from "react";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/**
 * 168 hours of the week, as a heat grid.
 *
 * A line chart over 168 points reads as noise; the grid puts every Tuesday 08:00
 * in the same column, which is how a weekly pattern actually becomes visible.
 * Departures and arrivals are shown separately rather than netted: a station
 * that takes 400 and gives back 400 is not the same as one that does neither,
 * and a net figure cannot tell them apart.
 */
export default function WeekProfile({ dep, arr }: { dep: number[]; arr: number[] }) {
  const [mode, setMode] = useState<"dep" | "arr">("dep");
  const [hover, setHover] = useState<number | null>(null);

  const series = mode === "dep" ? dep : arr;
  const max = Math.max(...series, 1);

  return (
    <div>
      <div style={{ display: "flex", gap: 10, marginBottom: 14, alignItems: "center" }}>
        {(["dep", "arr"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            style={{
              background: mode === m ? "var(--accent)" : "transparent",
              color: mode === m ? "#fff" : "var(--muted)",
              border: "1px solid " + (mode === m ? "var(--accent)" : "var(--line)"),
              borderRadius: 6, padding: "5px 12px", fontSize: 13, cursor: "pointer",
            }}
          >
            {m === "dep" ? "Departures" : "Arrivals"}
          </button>
        ))}
        <span style={{ marginLeft: "auto", fontSize: 13, color: "var(--dim)", fontFamily: "var(--mono)" }}>
          {hover !== null
            ? `${DAYS[Math.floor(hover / 24)]} ${String(hover % 24).padStart(2, "0")}:00 — ${series[hover].toLocaleString()}`
            : `peak ${max.toLocaleString()} in one hour-of-week`}
        </span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "38px 1fr", gap: 6 }}>
        <div />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(24, 1fr)", gap: 2, fontSize: 10, color: "var(--dim)" }}>
          {Array.from({ length: 24 }, (_, h) => (
            <div key={h} style={{ textAlign: "center" }}>{h % 6 === 0 ? h : ""}</div>
          ))}
        </div>

        {DAYS.map((d, di) => (
          <>
            <div key={d} style={{ fontSize: 12, color: "var(--muted)", lineHeight: "20px" }}>{d}</div>
            <div key={d + "row"} style={{ display: "grid", gridTemplateColumns: "repeat(24, 1fr)", gap: 2 }}>
              {Array.from({ length: 24 }, (_, h) => {
                const i = di * 24 + h;
                const v = series[i] / max;
                return (
                  <div
                    key={i}
                    onMouseEnter={() => setHover(i)}
                    onMouseLeave={() => setHover(null)}
                    title={`${d} ${String(h).padStart(2, "0")}:00 — ${series[i].toLocaleString()}`}
                    style={{
                      height: 20, borderRadius: 2,
                      background: `color-mix(in srgb, var(--accent) ${Math.round(v * 100)}%, var(--panel))`,
                      border: "1px solid var(--line)", cursor: "pointer",
                    }}
                  />
                );
              })}
            </div>
          </>
        ))}
      </div>
    </div>
  );
}
