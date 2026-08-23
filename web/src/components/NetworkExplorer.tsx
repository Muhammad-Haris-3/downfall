"use client";

import { useEffect, useRef, useState } from "react";
import "leaflet/dist/leaflet.css";
import StationPanel from "./StationPanel";

export type Station = {
  s: string; n: string; lat: number; lon: number;
  cap: number | null; dep: number; arr: number; rank: number; top200: boolean;
};
export type Profiles = Record<string, { dep: number[]; arr: number[] }>;

const CARTO_LIGHT = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";
const CARTO_DARK = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";
const ATTRIB =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> ' +
  '&copy; <a href="https://carto.com/attributions">CARTO</a>';

/**
 * Search, map and station detail as one component, because they share one
 * selection. A search result and a clicked dot resolve to the same place - the
 * station panel - rather than being two different ways of arriving somewhere.
 *
 * Detail opens as an overlay rather than a route. The map is the context for
 * every station, and navigating away to read one and back to find the next
 * throws that context away each time. The standalone `/station/<id>/` pages
 * still exist and render the same panel, so a shared link keeps working.
 */
export default function NetworkExplorer({
  stations,
  profiles,
}: {
  stations: Station[];
  profiles: Profiles;
}) {
  const el = useRef<HTMLDivElement>(null);
  const mapRef = useRef<import("leaflet").Map | null>(null);
  const layerRef = useRef<import("leaflet").LayerGroup | null>(null);
  const tileRef = useRef<import("leaflet").TileLayer | null>(null);
  const markers = useRef(new Map<string, import("leaflet").CircleMarker>());
  const onlyTopRef = useRef(false);

  const [onlyTop, setOnlyTop] = useState(false);
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const [focused, setFocused] = useState(false);
  const [hover, setHover] = useState<Station | null>(null);
  const [picked, setPicked] = useState<Station | null>(null);

  const q = query.trim().toLowerCase();
  // Ranked by traffic, so "broadway" surfaces the Broadway people mean before
  // the twenty they do not.
  const results = q.length < 2 ? [] :
    stations.filter((s) => s.n.toLowerCase().includes(q)).slice(0, 7);

  useEffect(() => { onlyTopRef.current = onlyTop; }, [onlyTop]);

  useEffect(() => {
    let dead = false;
    (async () => {
      const L = (await import("leaflet")).default;
      if (dead || !el.current || mapRef.current) return;

      const map = L.map(el.current, { preferCanvas: true, zoomControl: true })
        .setView([40.735, -73.96], 12);
      const isDark = document.documentElement.getAttribute("data-theme") === "dark";
      tileRef.current = L.tileLayer(isDark ? CARTO_DARK : CARTO_LIGHT, {
        attribution: ATTRIB, subdomains: "abcd", maxZoom: 18,
      }).addTo(map);

      mapRef.current = map;
      layerRef.current = L.layerGroup().addTo(map);

      // Leaflet reads the container's size when it computes a zoom, and on the
      // first paint that size is not final - fitBounds before it settles framed
      // New Jersey with every station off screen. Re-measured on the next frame
      // and on every resize after.
      const fit = () => {
        map.invalidateSize();
        map.fitBounds(
          L.latLngBounds(stations.map((s) => [s.lat, s.lon] as [number, number])),
          { padding: [26, 26] },
        );
      };
      requestAnimationFrame(fit);
      const ro = new ResizeObserver(() => map.invalidateSize());
      ro.observe(el.current);

      draw(L, map);
      map.on("zoomend", () => draw(L, map));

      // The tile set follows the theme toggle without rebuilding the map.
      const mo = new MutationObserver(() => {
        const d = document.documentElement.getAttribute("data-theme") === "dark";
        tileRef.current?.setUrl(d ? CARTO_DARK : CARTO_LIGHT);
      });
      mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

      return () => { ro.disconnect(); mo.disconnect(); };
    })();
    return () => { dead = true; mapRef.current?.remove(); mapRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    (async () => {
      const L = (await import("leaflet")).default;
      if (mapRef.current) draw(L, mapRef.current);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onlyTop]);

  function draw(L: typeof import("leaflet"), map: import("leaflet").Map) {
    const layer = layerRef.current;
    if (!layer) return;
    layer.clearLayers();
    markers.current.clear();

    const maxDep = Math.max(...stations.map((d) => d.dep), 1);
    // Markers grow with zoom, or zooming in only spreads the same tiny dots
    // further apart and reveals nothing.
    const k = Math.max(0.55, (map.getZoom() - 10) * 0.42);
    const shown = onlyTopRef.current ? stations.filter((s) => s.top200) : stations;

    for (const st of [...shown.filter((s) => !s.top200), ...shown.filter((s) => s.top200)]) {
      const m = L.circleMarker([st.lat, st.lon], {
        radius: (1.6 + 5.2 * Math.sqrt(st.dep / maxDep)) * k,
        stroke: false,
        fillColor: st.top200 ? "#ec3013" : "#7d7979",
        fillOpacity: st.top200 ? 0.88 : 0.4,
      });
      m.on("mouseover", () => setHover(st));
      m.on("mouseout", () => setHover(null));
      m.bindTooltip(
        `<strong>${st.n}</strong><br>${st.dep.toLocaleString()} departures · rank ${st.rank}` +
          (st.top200 ? "<br><em>click to open</em>" : ""),
        { direction: "top", opacity: 0.97 },
      );
      if (st.top200) m.on("click", () => setPicked(st));
      m.addTo(layer);
      markers.current.set(st.s, m);
    }
  }

  /** One destination for a click and for a search result alike. */
  function reveal(st: Station) {
    const map = mapRef.current;
    if (!map) return;
    if (onlyTop && !st.top200) setOnlyTop(false);
    map.flyTo([st.lat, st.lon], Math.max(map.getZoom(), 15), { duration: 0.7 });
    map.once("moveend", () => markers.current.get(st.s)?.openTooltip());
    setQuery("");
    setCursor(0);
    setFocused(false);
    if (st.top200) setPicked(st);
  }

  function onKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Escape") { setQuery(""); return; }
    if (!results.length) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => (c + 1) % results.length); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => (c - 1 + results.length) % results.length); }
    else if (e.key === "Enter") { e.preventDefault(); reveal(results[cursor]); }
  }

  const showResults = focused && q.length >= 2;

  return (
    <div>
      <div style={{ position: "relative", marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, border: "2px solid var(--line)", background: "var(--raise)", padding: "0 16px", transition: "border-color .25s ease" }}>
          <span aria-hidden style={{ fontSize: 17, color: "var(--dim)" }}>⌕</span>
          <input
            value={query}
            onChange={(e) => { setQuery(e.target.value); setCursor(0); }}
            onKeyDown={onKey}
            onFocus={() => setFocused(true)}
            onBlur={() => setTimeout(() => setFocused(false), 120)}
            placeholder={`Search ${stations.length.toLocaleString()} stations — try Broadway, Pier, Bedford`}
            aria-label="Search stations by name"
            style={{ flex: 1, padding: "15px 0", fontFamily: "inherit", fontSize: 15.5, background: "none", border: 0, color: "var(--ink)", outline: "none" }}
          />
          {query && (
            <button onClick={() => setQuery("")} style={{ background: "none", border: 0, fontFamily: "inherit", fontSize: 11, fontWeight: 700, letterSpacing: ".1em", color: "var(--dim)", cursor: "pointer" }}>CLEAR</button>
          )}
        </div>

        {showResults && (
          <div style={{ position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, background: "var(--raise)", border: "2px solid var(--line)", zIndex: 500, boxShadow: "var(--sh-lg)" }}>
            {results.length === 0 && (
              <div style={{ padding: "14px 18px", color: "var(--dim)", fontSize: 14 }}>Nothing matches that.</div>
            )}
            {results.map((st, i) => (
              <button
                key={st.s}
                onMouseDown={(e) => { e.preventDefault(); reveal(st); }}
                onMouseEnter={() => setCursor(i)}
                style={{
                  display: "flex", width: "100%", gap: 12, alignItems: "baseline",
                  padding: "12px 18px", textAlign: "left", cursor: "pointer",
                  background: i === cursor ? "var(--accent-soft)" : "transparent",
                  border: 0, borderBottom: "1px solid var(--line)",
                  color: "var(--ink)", fontFamily: "inherit", fontSize: 14.5,
                }}
              >
                <span aria-hidden style={{ width: 7, height: 7, background: st.top200 ? "var(--accent)" : "var(--dim)" }} />
                <span style={{ flex: 1, fontWeight: 600 }}>{st.n}</span>
                {st.top200 && <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: ".1em", color: "var(--accent)" }}>HAS A PAGE</span>}
                <span className="num" style={{ fontSize: 12.5, color: "var(--muted)" }}>{st.dep.toLocaleString()} · #{st.rank}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
        <button
          onClick={() => setOnlyTop((v) => !v)}
          style={{ display: "inline-flex", alignItems: "center", gap: 10, background: "transparent", border: "2px solid var(--line)", padding: "8px 13px", cursor: "pointer", fontFamily: "inherit", fontSize: 13, fontWeight: 600, color: "var(--ink)" }}
        >
          <span aria-hidden style={{ width: 11, height: 11, background: onlyTop ? "var(--accent)" : "transparent", border: "2px solid " + (onlyTop ? "var(--accent)" : "var(--line)") }} />
          Only the 200 busiest
        </button>
        <span style={{ fontSize: 12.5, color: "var(--dim)", marginLeft: "auto" }}>
          {(onlyTop ? 200 : stations.length).toLocaleString()} shown · scroll to zoom · click a red dot
        </span>
      </div>

      <div ref={el} style={{ height: "min(74vh, 760px)", border: "2px solid var(--divider)", background: "var(--surface)", zIndex: 0 }} />

      <div style={{ display: "flex", gap: 22, marginTop: 12, fontSize: 12.5, color: "var(--muted)", flexWrap: "wrap" }}>
        <span><span aria-hidden style={{ display: "inline-block", width: 9, height: 9, background: "var(--accent)", marginRight: 7 }} />200 busiest — each has a page</span>
        <span><span aria-hidden style={{ display: "inline-block", width: 9, height: 9, background: "var(--dim)", opacity: .6, marginRight: 7 }} />the other {(stations.length - 200).toLocaleString()}</span>
        <span style={{ marginLeft: "auto", color: "var(--dim)" }}>
          {hover ? `${hover.n} — ${hover.dep.toLocaleString()} departures` : "dot area ∝ trips recorded"}
        </span>
      </div>

      {picked && (
        <StationPanel
          station={picked}
          profile={profiles[picked.s]}
          onClose={() => setPicked(null)}
        />
      )}
    </div>
  );
}
