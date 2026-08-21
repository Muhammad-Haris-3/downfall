import fs from "node:fs";
import path from "node:path";
import NetworkMap, { Station } from "@/components/NetworkMap";

type Network = {
  built_at: string;
  window: [string, string];
  stations: number;
  unresolved_stations: number;
  total_departures: number;
  network: Station[];
};

function load(): Network {
  const p = path.join(process.cwd(), "public", "data", "network.json");
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

const fmtMonth = (m: string) =>
  new Date(+m.slice(0, 4), +m.slice(4) - 1).toLocaleString("en", {
    month: "short",
    year: "numeric",
  });

export default function Home() {
  const data = load();
  const top = data.network.slice(0, 8);

  return (
    <main className="wrap">
      <div className="hero">
        <span className="status">
          <span className="dot" />
          M0 complete · collecting · no demand estimate published
        </span>
        <h1>A station with no bikes records no demand.</h1>
        <p className="lede">
          Every dot below is sized by the number of departures the trip archive
          recorded there. That is the measure essentially every published
          analysis of this dataset uses.
        </p>
        <p className="lede">
          <strong>It is wrong in a specific direction.</strong> A rider who
          arrives at an empty dock and walks away leaves no trace, because the
          only event the system can record is a trip that happened. So the
          stations that fail most often look, in this data, like the stations
          nobody wants — and get resourced accordingly.
        </p>
      </div>

      <section>
        <h2>The network as the data sees it</h2>
        <p className="sub">
          {data.stations.toLocaleString()} stations,{" "}
          {(data.total_departures / 1e6).toFixed(1)} million departures recorded
          between {fmtMonth(data.window[0])} and {fmtMonth(data.window[1])}.
        </p>
        <NetworkMap stations={data.network} />

        <div className="note">
          <strong>What this map cannot yet show.</strong> The measure worth
          seeing is not how many trips a station recorded but how often it was
          unusable — a snapshot is weather, the rate is climate, and the rate is
          what an operator can act on. That requires 21 continuous days of
          observation at 95% coverage, a floor fixed in{" "}
          <a href="https://github.com/Muhammad-Haris-3/downfall/blob/main/PREREGISTRATION.md">
            pre-registration
          </a>{" "}
          before any data existed. Collection is running. Until the floor is met
          this page shows what was recorded, and says so.
        </div>
      </section>

      <section>
        <h2>Busiest stations, by departures recorded</h2>
        <p className="sub">
          Ranked over the twelve months before observation began — deliberately,
          so that the ranking cannot be affected by the outages being measured.
        </p>
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th className="num">#</th>
                <th>Station</th>
                <th className="num">Departures</th>
                <th className="num">Arrivals</th>
                <th className="num">Docks</th>
              </tr>
            </thead>
            <tbody>
              {top.map((s) => (
                <tr key={s.s}>
                  <td className="num">{s.rank}</td>
                  <td>
                    <a href={`/station/${encodeURIComponent(s.s)}/`}>{s.n}</a>
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

      <section>
        <h2>What has been established</h2>
        <p className="sub">
          Every figure measured, and recorded in{" "}
          <a href="https://github.com/Muhammad-Haris-3/downfall/blob/main/FINDINGS.md">
            FINDINGS.md
          </a>{" "}
          in the order it was established.
        </p>
        <div className="grid">
          <div className="card">
            <div className="k">Publish cycle</div>
            <div className="v">70s</div>
            <div className="d">Exactly, nine gaps with no variance. Polling faster returns an identical file.</div>
          </div>
          <div className="card">
            <div className="k">Median stockout</div>
            <div className="v">9.9 min</div>
            <div className="d">Kaplan–Meier over one evening peak. 16% were still empty after an hour.</div>
          </div>
          <div className="card">
            <div className="k">Trips joined to a station</div>
            <div className="v">98.1%</div>
            <div className="d">Measured on 1.2M February trips. <code>short_name</code> is the bridge.</div>
          </div>
          <div className="card">
            <div className="k">Trips aggregated</div>
            <div className="v">115.0M</div>
            <div className="d">31 months, 22.5 GB of archive, reduced to 97 MB of counts.</div>
          </div>
        </div>
      </section>

      <section>
        <h2>Why this can be checked rather than argued</h2>
        <p className="sub">
          The tempting version of this project asserts a hidden number and asks
          to be believed. This one does not have to.
        </p>
        <p style={{ maxWidth: "68ch", color: "var(--muted)" }}>
          Some stations never run out. For those, observed demand{" "}
          <em>is</em> true demand — the answer is already on the table. So the
          method can be marked: take a station that never stocked out, hide its
          data during the hours a comparable station was empty, re-estimate, and
          see whether the number it recovers is the number that was there all
          along. The thresholds it has to clear were written down before the
          estimator existed.
        </p>
        <div className="note">
          <strong>The deliverable is not the demand estimate.</strong> It is the
          error of that estimate against cases where the truth was already
          known — and if it fails, the claim is withdrawn rather than caveated.
        </div>
      </section>
    </main>
  );
}
