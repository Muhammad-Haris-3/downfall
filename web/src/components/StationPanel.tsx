"use client";

import { useEffect, useRef, useState } from "react";
import type { Station } from "./NetworkExplorer";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/**
 * One station's record, as an overlay.
 *
 * The week grid puts every Tuesday 08:00 in the same column, which is how a
 * weekly pattern becomes visible at all - 168 points on a line read as noise.
 * Departures and arrivals are shown separately rather than netted: a station
 * that takes 400 and returns 400 is not the same as one that does neither, and
 * a net figure cannot tell them apart.
 *
 * Two of the four cards read "—" on purpose. They are the project.
 */
export default function StationPanel({
  station,
  profile,
  onClose,
  embedded = false,
}: {
  station: Station;
  profile?: { dep: number[]; arr: number[] };
  onClose?: () => void;
  embedded?: boolean;
}) {
  const [mode, setMode] = useState<"dep" | "arr">("dep");
  const [cell, setCell] = useState<number | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (embedded) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose?.(); };
    document.addEventListener("keydown", onKey);
    // The overlay takes focus so the keyboard is not left behind on the map.
    closeRef.current?.focus();
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [embedded, onClose]);

  const series = profile ? (mode === "dep" ? profile.dep : profile.arr) : [];
  const max = Math.max(...series, 1);
  const peak = series.indexOf(Math.max(...series));

  const body = (
    <div style={{ background: "var(--bg)", border: embedded ? "none" : "2px solid var(--divider)", boxShadow: embedded ? "none" : "var(--sh-lg)", maxWidth: 980, width: "100%", maxHeight: embedded ? "none" : "88vh", overflowY: embedded ? "visible" : "auto" }}>
      <div style={{ padding: "28px 32px", borderBottom: "2px solid var(--divider)", display: "flex", gap: 24, alignItems: "flex-start" }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
            <span aria-hidden style={{ width: 7, height: 7, background: "var(--accent)" }} />
            <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".13em", textTransform: "uppercase", color: "var(--muted)" }}>
              Rank {station.rank} by trips recorded
            </span>
          </div>
          <h2 style={{ fontSize: "clamp(26px,3.4vw,40px)", marginBottom: 10 }}>{station.n}</h2>
          <p style={{ fontSize: 15.5, color: "var(--muted)", margin: 0, maxWidth: "60ch" }}>
            {station.dep.toLocaleString()} departures and {station.arr.toLocaleString()} arrivals
            recorded over twelve months.
          </p>
        </div>
        {!embedded && (
          <button ref={closeRef} onClick={onClose} aria-label="Close"
            style={{ width: 40, height: 40, flexShrink: 0, background: "transparent", border: "2px solid var(--line)", color: "var(--ink)", fontSize: 20, lineHeight: 1, cursor: "pointer", transition: "background .25s ease, transform .25s ease" }}>
            ×
          </button>
        )}
      </div>

      <div style={{ padding: "28px 32px" }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 18, flexWrap: "wrap" }}>
          {(["dep", "arr"] as const).map((m) => (
            <button key={m} onClick={() => setMode(m)}
              style={{
                background: mode === m ? "var(--accent)" : "transparent",
                color: mode === m ? "#fff" : "var(--muted)",
                border: "2px solid " + (mode === m ? "var(--accent)" : "var(--line)"),
                padding: "7px 14px", fontFamily: "inherit", fontSize: 13, fontWeight: 700, cursor: "pointer",
              }}>
              {m === "dep" ? "Departures" : "Arrivals"}
            </button>
          ))}
          <span className="num" style={{ marginLeft: "auto", fontSize: 12.5, color: "var(--dim)" }}>
            {cell !== null
              ? `${DAYS[Math.floor(cell / 24)]} ${String(cell % 24).padStart(2, "0")}:00 — ${series[cell]?.toLocaleString()}`
              : `busiest ${DAYS[Math.floor(peak / 24)]} ${String(peak % 24).padStart(2, "0")}:00`}
          </span>
        </div>

        {profile ? (
          <div style={{ display: "grid", gridTemplateColumns: "42px 1fr", gap: 6 }}>
            <div />
            <div style={{ display: "grid", gridTemplateColumns: "repeat(24,1fr)", gap: 2, fontSize: 9.5, color: "var(--dim)" }}>
              {Array.from({ length: 24 }, (_, h) => (
                <div key={h} style={{ textAlign: "center" }}>{h % 6 === 0 ? h : ""}</div>
              ))}
            </div>
            {DAYS.map((d, di) => (
              <div key={d} style={{ display: "contents" }}>
                <div style={{ fontSize: 11.5, color: "var(--muted)", lineHeight: "20px", fontWeight: 600 }}>{d}</div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(24,1fr)", gap: 2 }}>
                  {Array.from({ length: 24 }, (_, h) => {
                    const i = di * 24 + h;
                    const v = (series[i] ?? 0) / max;
                    return (
                      <div key={i}
                        onMouseEnter={() => setCell(i)}
                        onMouseLeave={() => setCell(null)}
                        title={`${d} ${String(h).padStart(2, "0")}:00 — ${(series[i] ?? 0).toLocaleString()}`}
                        style={{
                          height: 20,
                          background: v === 0 ? "var(--surface)" : `color-mix(in srgb, var(--accent) ${Math.round(12 + v * 88)}%, var(--surface))`,
                          cursor: "pointer",
                        }} />
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p style={{ color: "var(--dim)" }}>No weekly profile for this station.</p>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(190px,1fr))", gap: 16, marginTop: 30 }}>
          <div className="card">
            <div className="k">Departures recorded</div>
            <div className="v">{(station.dep / 1000).toFixed(1)}k</div>
            <div className="d">Trips that started here and were counted.</div>
          </div>
          <div className="card">
            <div className="k">Docks</div>
            <div className="v">{station.cap ?? "—"}</div>
            <div className="d">Capacity as the live feed reports it.</div>
          </div>
          <div className="card">
            <div className="k">Hours unusable</div>
            <div className="v" style={{ color: "var(--dim)" }}>—</div>
            <div className="d">Not published. Needs the coverage floor in §3 of the pre-registration.</div>
          </div>
          <div className="card">
            <div className="k">Estimated true demand</div>
            <div className="v" style={{ color: "var(--dim)" }}>—</div>
            <div className="d">Not published. Needs an estimator that has passed §4.</div>
          </div>
        </div>

        <div className="note" style={{ marginTop: 26 }}>
          <strong>The two blank cards are the project.</strong> Everything the
          trip archive alone can tell you sits above them, and none of it says
          how many people wanted a bike here and did not get one. That number is
          not small, it is not random, and it is in no published dataset.
        </div>
      </div>
    </div>
  );

  if (embedded) return body;

  return (
    <div
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={station.n}
      style={{
        position: "fixed", inset: 0, zIndex: 900,
        background: "rgba(0,0,0,.55)", backdropFilter: "blur(3px)",
        display: "flex", alignItems: "center", justifyContent: "center", padding: 24,
        animation: "fade .25s ease both",
      }}
    >
      <div onClick={(e) => e.stopPropagation()} style={{ width: "100%", maxWidth: 980, animation: "rise .35s cubic-bezier(.2,.7,.2,1) both" }}>
        {body}
      </div>
    </div>
  );
}
