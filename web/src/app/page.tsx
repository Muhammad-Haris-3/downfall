import fs from "node:fs";
import path from "node:path";
import NetworkExplorer, { Station } from "@/components/NetworkExplorer";
import Reveal from "@/components/Reveal";

type Network = {
  built_at: string;
  window: [string, string];
  stations: number;
  total_departures: number;
  network: Station[];
};

type Profiles = Record<string, { dep: number[]; arr: number[] }>;

function load() {
  const root = process.cwd();
  const net: Network = JSON.parse(
    fs.readFileSync(path.join(root, "public", "data", "network.json"), "utf8"),
  );
  const profiles: Profiles = JSON.parse(
    fs.readFileSync(path.join(root, "data", "profiles.json"), "utf8"),
  );
  // Only the cohort has a detail view, so only the cohort's profiles are
  // shipped. The full file is 2.5 MB and the browser has no use for the rest.
  const slim: Profiles = {};
  for (const s of net.network) if (s.top200) slim[s.s] = profiles[s.s];
  return { net, profiles: slim };
}

const fmtMonth = (m: string) =>
  new Date(+m.slice(0, 4), +m.slice(4) - 1).toLocaleString("en", { month: "short", year: "numeric" });

const STATS = [
  { k: "Publish cycle", v: "70s", d: "Exactly. Nine gaps with no variance — polling faster returns an identical file." },
  { k: "Median stockout", v: "9.9 min", d: "Kaplan–Meier over one evening peak. 16% were still empty after an hour." },
  { k: "Trips joined to a station", v: "98.1%", d: "Measured on 1.2M February trips. short_name is the bridge; station_id is not." },
  { k: "Trips aggregated", v: "115.0M", d: "31 months, 22.5 GB of archive, reduced to 97 MB of counts." },
];

export default function Home() {
  const { net, profiles } = load();
  const top = net.network.slice(0, 10);

  return (
    <>
      <section style={{ padding: "96px 32px 72px" }}>
        <Reveal>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 9, border: "2px solid var(--line)", padding: "6px 13px", marginBottom: 34 }}>
            <span aria-hidden style={{ width: 7, height: 7, background: "var(--accent)", animation: "blink 1.8s ease-in-out infinite" }} />
            <span style={{ fontSize: 11.5, fontWeight: 700, letterSpacing: ".14em", textTransform: "uppercase", color: "var(--muted)" }}>
              M0 complete · collecting · nothing ranked yet
            </span>
          </div>
        </Reveal>

        <Reveal delay={0.06}>
          <h1 style={{ margin: "0 0 34px", maxWidth: "16ch" }}>
            An empty dock<br />records <span style={{ color: "var(--accent)" }}>no demand</span>.
          </h1>
        </Reveal>

        <Reveal delay={0.14}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(300px,1fr))", gap: 40, maxWidth: 960 }}>
            <p style={{ fontSize: 19, lineHeight: 1.5, color: "var(--muted)", margin: 0 }}>
              Forty people find an empty rack. Ten trips get written down. The
              other thirty leave no row anywhere, because a trip that never
              happened is not an event.
            </p>
            <p style={{ fontSize: 19, lineHeight: 1.5, color: "var(--muted)", margin: 0 }}>
              <strong style={{ color: "var(--ink)", fontWeight: 700 }}>The error runs one way.</strong>{" "}
              Stations that fail most look quietest, so they get fewer bikes, so
              they fail sooner. The measurement causes the outcome it describes.
            </p>
          </div>
        </Reveal>

        <Reveal delay={0.22}>
          <div style={{ display: "flex", gap: 14, marginTop: 44, flexWrap: "wrap" }}>
            <a className="btn btn-primary" href="#network">See the network <span style={{ fontWeight: 800 }}>↓</span></a>
            <a className="btn btn-ghost" href="/method/">How it stays honest</a>
          </div>
        </Reveal>
      </section>

      <div className="rule" />

      <section id="network">
        <div style={{ display: "flex", gap: 40, flexWrap: "wrap", alignItems: "flex-end", marginBottom: 34 }}>
          <div>
            <div className="kicker">01 — The record</div>
            <h2>The network as the data sees it</h2>
          </div>
          <p style={{ fontSize: 15.5, color: "var(--muted)", margin: 0, maxWidth: "46ch", marginLeft: "auto" }}>
            {net.stations.toLocaleString()} stations. {(net.total_departures / 1e6).toFixed(1)}M
            departures, {fmtMonth(net.window[0])} – {fmtMonth(net.window[1])}. Dot
            area is trips recorded — the measure this project argues is wrong.
          </p>
        </div>

        <NetworkExplorer stations={net.network} profiles={profiles} />
      </section>

      <div className="rule" />

      <section>
        <div className="kicker">02 — Ranked</div>
        <h2 style={{ marginBottom: 14 }}>Busiest stations, by trips recorded</h2>
        <p style={{ fontSize: 15.5, color: "var(--muted)", maxWidth: "70ch", marginTop: 0, marginBottom: 30 }}>
          Ranked over the twelve months before observation began, so the ranking
          cannot be moved by the outages being measured.
        </p>
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th className="num" style={{ width: 60 }}>#</th>
                <th>Station</th>
                <th className="num">Departures</th>
                <th className="num">Arrivals</th>
                <th className="num">Docks</th>
              </tr>
            </thead>
            <tbody>
              {top.map((s) => (
                <tr key={s.s}>
                  <td className="num" style={{ color: "var(--accent)", fontWeight: 700 }}>{s.rank}</td>
                  <td style={{ fontWeight: 600 }}>
                    <a href={`/station/${encodeURIComponent(s.s)}/`} style={{ color: "var(--ink)" }}>{s.n}</a>
                  </td>
                  <td className="num">{s.dep.toLocaleString()}</td>
                  <td className="num">{s.arr.toLocaleString()}</td>
                  <td className="num">{s.cap ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="rule" />

      <section>
        <div className="kicker">03 — Established</div>
        <h2 style={{ marginBottom: 30 }}>Four numbers that are measured, not claimed</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))", gap: 20 }}>
          {STATS.map((s, i) => (
            <Reveal key={s.k} delay={i * 0.06}>
              <div className="card" style={{ height: "100%" }}>
                <div className="k">{s.k}</div>
                <div className="v" style={{ color: "var(--accent)" }}>{s.v}</div>
                <div className="d">{s.d}</div>
              </div>
            </Reveal>
          ))}
        </div>
        <p style={{ fontSize: 13.5, color: "var(--dim)", marginTop: 22 }}>
          Every figure recorded in{" "}
          <a href="https://github.com/Muhammad-Haris-3/downfall/blob/main/FINDINGS.md">FINDINGS.md</a>{" "}
          in the order it was established, including the ones that went wrong.
        </p>
      </section>

      {/* The poster close — the one place the accent runs as a field. */}
      <section style={{ background: "var(--accent)", color: "#fff", maxWidth: "none", padding: "88px 0", marginTop: 16 }}>
        <div className="wrap">
          <h2 style={{ fontSize: "clamp(30px,4.4vw,56px)", maxWidth: "24ch", marginBottom: 22 }}>
            The deliverable is not the demand estimate. It is the error of that
            estimate against cases where the truth was already known.
          </h2>
          <p style={{ fontSize: 18, maxWidth: "62ch", opacity: .92, margin: "0 0 30px" }}>
            Some stations never run out. For those, observed demand <em>is</em>{" "}
            true demand — so the method can be marked against an answer that was
            on the table the whole time. If it fails, the claim is withdrawn
            rather than caveated.
          </p>
          <a className="btn" href="/method/" style={{ background: "#fff", color: "var(--accent)" }}>
            Read the method
          </a>
        </div>
      </section>
    </>
  );
}
