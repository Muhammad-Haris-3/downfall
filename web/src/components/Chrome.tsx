"use client";

import { useEffect, useState } from "react";

/**
 * The header, the animated ground and the theme toggle.
 *
 * The mesh and the grid are fixed behind everything at negative z-index and are
 * `aria-hidden` — they carry no information, and a screen reader announcing
 * three drifting gradients would be worse than silence. Both are suppressed
 * entirely under `prefers-reduced-motion` by the stylesheet.
 *
 * The theme is stored and applied to <html> rather than read from
 * `prefers-color-scheme`: the palette is part of the argument this site makes,
 * and a reader who has chosen one should not have the other imposed by their
 * operating system.
 */
const NAV = [
  { href: "/", label: "Network" },
  { href: "/conditions/", label: "Conditions" },
  { href: "/method/", label: "Method" },
];

export function Background() {
  return (
    <>
      <div aria-hidden style={{ position: "fixed", inset: 0, zIndex: -2, pointerEvents: "none", overflow: "hidden" }}>
        <div style={{ position: "absolute", top: "-25%", left: "-15%", width: "75vw", height: "75vw", background: "radial-gradient(circle at 50% 50%, var(--mesh-a), transparent 62%)", filter: "blur(30px)", animation: "drift-a 34s ease-in-out infinite" }} />
        <div style={{ position: "absolute", top: "20%", right: "-25%", width: "70vw", height: "70vw", background: "radial-gradient(circle at 50% 50%, var(--mesh-b), transparent 64%)", filter: "blur(34px)", animation: "drift-b 44s ease-in-out infinite" }} />
        <div style={{ position: "absolute", bottom: "-30%", left: "25%", width: "60vw", height: "60vw", background: "radial-gradient(circle at 50% 50%, var(--mesh-a), transparent 66%)", filter: "blur(40px)", animation: "drift-c 52s ease-in-out infinite" }} />
      </div>
      <div aria-hidden style={{ position: "fixed", inset: 0, zIndex: -1, pointerEvents: "none", backgroundImage: "linear-gradient(var(--grid) 1px, transparent 1px), linear-gradient(90deg, var(--grid) 1px, transparent 1px)", backgroundSize: "80px 80px" }} />
    </>
  );
}

export function Header({ path }: { path: string }) {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("downfall-theme");
    const isDark = saved === "dark";
    setDark(isDark);
    document.documentElement.setAttribute("data-theme", isDark ? "dark" : "light");
  }, []);

  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.setAttribute("data-theme", next ? "dark" : "light");
    localStorage.setItem("downfall-theme", next ? "dark" : "light");
  }

  return (
    <header style={{
      position: "sticky", top: 0, zIndex: 60,
      borderBottom: "2px solid var(--divider)",
      background: "color-mix(in srgb, var(--bg) 82%, transparent)",
      backdropFilter: "blur(14px) saturate(1.2)",
      WebkitBackdropFilter: "blur(14px) saturate(1.2)",
    }}>
      <div className="wrap" style={{ height: 70, display: "flex", alignItems: "center", gap: 32 }}>
        <a href="/" style={{ display: "flex", alignItems: "center", gap: 11, color: "var(--ink)" }}>
          <span aria-hidden style={{ width: 13, height: 13, background: "var(--accent)", display: "block", animation: "blink 2.6s ease-in-out infinite" }} />
          <span style={{ fontSize: 19, fontWeight: 800, letterSpacing: "-.035em", textTransform: "uppercase" }}>Downfall</span>
        </a>

        <nav style={{ display: "flex", gap: 4, marginLeft: "auto", alignItems: "center" }}>
          {NAV.map((n) => {
            const active = path === n.href;
            return (
              <a key={n.href} href={n.href} style={{
                padding: "9px 14px", fontSize: 13.5, fontWeight: 600, letterSpacing: ".01em",
                color: active ? "var(--ink)" : "var(--muted)",
                borderBottom: active ? "2px solid var(--accent)" : "2px solid transparent",
              }}>{n.label}</a>
            );
          })}
          <a href="https://github.com/Muhammad-Haris-3/downfall"
             style={{ padding: "9px 14px", fontSize: 13.5, fontWeight: 600, color: "var(--muted)" }}>Source</a>
          <button onClick={toggle} aria-label="Toggle light and dark" style={{
            marginLeft: 12, width: 38, height: 38, display: "flex", alignItems: "center", justifyContent: "center",
            background: "transparent", border: "2px solid var(--line)", color: "var(--ink)", cursor: "pointer",
            transition: "background .25s ease, border-color .25s ease, transform .25s cubic-bezier(.2,.7,.2,1)",
          }}>
            <span style={{ fontSize: 14, fontWeight: 700, lineHeight: 1 }}>{dark ? "☾" : "☀"}</span>
          </button>
        </nav>
      </div>
    </header>
  );
}

export function Footer() {
  return (
    <footer style={{ borderTop: "2px solid var(--divider)", marginTop: 24 }}>
      <div className="wrap" style={{ padding: "32px", display: "flex", gap: 20, flexWrap: "wrap", fontSize: 13, color: "var(--dim)" }}>
        <span>Muhammad Haris Khokhar</span>
        <span style={{ marginLeft: "auto" }}>
          Trips: Citi Bike system data · Availability: GBFS · Weather: Open-Meteo
        </span>
      </div>
    </footer>
  );
}
