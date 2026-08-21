"use client";

import { useEffect, useRef, useState } from "react";
import "leaflet/dist/leaflet.css";

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
 * The network on a real, pannable map.
 *
 * An earlier version drew the stations on a bare SVG with no basemap, and
 * argued that was better - that 2,391 dots draw the city's own shape and
 * streets would only distract. That was a rationalisation of a constraint
 * rather than a design decision, and it did not survive being looked at: the
 * result reads as a dot cloud, not a map, and there is nothing to zoom into.
 *
 * The constraint did not require it either. CARTO's basemaps are free and need
 * no account or API key, so NFR-1 is satisfied without giving up the map.
 *
 * Plain Leaflet rather than react-leaflet: one dependency instead of two, no
 * peer-dependency argument with React 19, and the imperative API is a better
 * fit for redrawing 2,391 markers on zoom than a component tree is.
 */
const CARTO_URL =
  "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";
const CARTO_LIGHT =
  "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";
const ATTRIB =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> ' +
  '&copy; <a href="https://carto.com/attributions">CARTO</a>';

export default function NetworkMap({ stations }: { stations: Station[] }) {
  const el = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<Station | null>(null);
  const [onlyTop, setOnlyTop] = useState(false);
  const mapRef = useRef<import("leaflet").Map | null>(null);
  const layerRef = useRef<import("leaflet").LayerGroup | null>(null);
  const roRef = useRef<ResizeObserver | null>(null);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      const L = (await import("leaflet")).default;
      if (cancelled || !el.current || mapRef.current) return;

      const dark = window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? true;
      const map = L.map(el.current, { preferCanvas: true, zoomControl: true })
        .setView([40.735, -73.96], 12);
      L.tileLayer(dark ? CARTO_URL : CARTO_LIGHT, {
        attribution: ATTRIB,
        subdomains: "abcd",
        maxZoom: 18,
      }).addTo(map);

      mapRef.current = map;
      layerRef.current = L.layerGroup().addTo(map);

      const bounds = L.latLngBounds(
        stations.map((s) => [s.lat, s.lon] as [number, number]),
      );

      // fitBounds computes a zoom from the container's CURRENT size, and on
      // first paint that size is not yet final - the first attempt framed New
      // Jersey and left every station off screen. invalidateSize() forces
      // Leaflet to re-measure, and a ResizeObserver keeps the framing right
      // when the window changes rather than only when the page loads.
      const frame = () => {
        map.invalidateSize();
        // Frame the network itself rather than a hard-coded centre, so a station
        // outside today's bounds does not quietly fall off the map.
        map.fitBounds(bounds, { padding: [22, 22] });
      };
      requestAnimationFrame(frame);

      const ro = new ResizeObserver(() => map.invalidateSize());
      ro.observe(el.current);
      roRef.current = ro;

      draw(L, map);
      map.on("zoomend", () => draw(L, map));
    })();

    return () => {
      cancelled = true;
      roRef.current?.disconnect();
      roRef.current = null;
      mapRef.current?.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Redraw when the filter changes, without rebuilding the map.
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

    const maxDep = Math.max(...stations.map((d) => d.dep), 1);
    const z = map.getZoom();
    // Markers grow with zoom, or zooming in only spreads the same tiny dots
    // further apart and reveals nothing.
    const k = Math.max(0.55, (z - 10) * 0.42);
    const shown = onlyTop ? stations.filter((s) => s.top200) : stations;

    // The cohort is added last so it draws above the stations it outranks.
    for (const st of [...shown.filter((s) => !s.top200), ...shown.filter((s) => s.top200)]) {
      const r = (1.6 + 5.2 * Math.sqrt(st.dep / maxDep)) * k;
      const m = L.circleMarker([st.lat, st.lon], {
        radius: r,
        stroke: st.top200,
        color: "#8ec5ff",
        weight: 1,
        fillColor: st.top200 ? "#4ea1ff" : "#8b97a6",
        fillOpacity: st.top200 ? 0.85 : 0.42,
        // Only the cohort has a page. A click that goes nowhere is worse than
        // one that does not invite itself.
        interactive: true,
      });
      m.on("mouseover", () => setHover(st));
      m.on("mouseout", () => setHover(null));
      m.bindTooltip(
        `<strong>${st.n}</strong><br>${st.dep.toLocaleString()} departures · rank ${st.rank}` +
          (st.top200 ? "<br><em>click for this station</em>" : ""),
        { direction: "top", opacity: 0.95 },
      );
      if (st.top200) {
        m.on("click", () => {
          window.location.href = `/station/${encodeURIComponent(st.s)}/`;
        });
      }
      m.addTo(layer);
    }
  }

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
          {(onlyTop ? 200 : stations.length).toLocaleString()} stations · scroll to zoom · drag to pan
        </span>
      </div>

      <div
        ref={el}
        style={{
          height: "min(74vh, 720px)",
          borderRadius: 10,
          border: "1px solid var(--line)",
          background: "var(--panel)",
          zIndex: 0,
        }}
      />

      <div style={{ display: "flex", gap: 20, marginTop: 10, fontSize: 13, color: "var(--muted)", flexWrap: "wrap" }}>
        <span>
          <span style={{ display: "inline-block", width: 9, height: 9, borderRadius: 5, background: "#4ea1ff", marginRight: 7 }} />
          200 busiest — click one for its own page
        </span>
        <span>
          <span style={{ display: "inline-block", width: 9, height: 9, borderRadius: 5, background: "#8b97a6", opacity: 0.6, marginRight: 7 }} />
          the rest
        </span>
        <span style={{ marginLeft: "auto", color: "var(--dim)" }}>
          {hover ? `${hover.n} — ${hover.dep.toLocaleString()} departures` : "dot area ∝ departures recorded"}
        </span>
      </div>
    </div>
  );
}
