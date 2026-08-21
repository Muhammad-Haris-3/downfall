import fs from "node:fs";
import path from "node:path";
import type { Station } from "@/components/NetworkMap";
import WeekProfile from "@/components/WeekProfile";

type Profiles = Record<string, { dep: number[]; arr: number[] }>;

function load() {
  const root = process.cwd();
  const net = JSON.parse(
    fs.readFileSync(path.join(root, "public", "data", "network.json"), "utf8"),
  ) as { network: Station[]; window: [string, string] };
  const profiles = JSON.parse(
    fs.readFileSync(path.join(root, "data", "profiles.json"), "utf8"),
  ) as Profiles;
  return { net, profiles };
}

/**
 * Pages are generated for the top-200 cohort only.
 *
 * Not a performance compromise. That cohort is the population the kill
 * criterion is evaluated on and the one an operator would actually act on, and
 * it was fixed from the twelve months preceding collection so that it cannot be
 * influenced by the outages being measured. Generating a page for every station
 * would imply all 2,391 are part of the analysis, and they are not.
 */
export function generateStaticParams() {
  const { net } = load();
  return net.network.filter((s) => s.top200).map((s) => ({ id: s.s }));
}

/** The station's own name in the tab and in any shared link, not the site's. */
export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const { net } = load();
  const st = net.network.find((s) => s.s === decodeURIComponent(id));
  if (!st) return { title: "Unknown station — Downfall" };
  return {
    title: `${st.n} — Downfall`,
    description:
      `${st.dep.toLocaleString()} departures recorded at ${st.n} over twelve ` +
      `months. How many were prevented by an empty dock is not yet published.`,
  };
}

export default async function StationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const { net, profiles } = load();
  const station = net.network.find((s) => s.s === decodeURIComponent(id));
  if (!station) return <main className="wrap"><h1>Unknown station</h1></main>;

  const prof = profiles[station.s];
  const totalDep = prof.dep.reduce((a, b) => a + b, 0);
  const peakIdx = prof.dep.indexOf(Math.max(...prof.dep));
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  return (
    <main className="wrap">
      <div className="hero" style={{ paddingBottom: 20 }}>
        <span className="status">
          <span className="dot" />
          rank {station.rank} of {net.network.length.toLocaleString()} by departures
        </span>
        <h1 style={{ fontSize: 34, marginTop: 18 }}>{station.n}</h1>
        <p className="lede">
          {station.dep.toLocaleString()} departures and{" "}
          {station.arr.toLocaleString()} arrivals recorded over the twelve months
          to {net.window[1].slice(0, 4)}-{net.window[1].slice(4)}.
        </p>
      </div>

      <section style={{ paddingTop: 24 }}>
        <h2>When this station is used</h2>
        <p className="sub">
          Departures by hour of the week, summed over twelve months. Busiest
          hour: {days[Math.floor(peakIdx / 24)]}{" "}
          {String(peakIdx % 24).padStart(2, "0")}:00.
        </p>
        <WeekProfile dep={prof.dep} arr={prof.arr} />
      </section>

      <section>
        <h2>What is recorded, and what is not</h2>
        <div className="grid">
          <div className="card">
            <div className="k">Departures recorded</div>
            <div className="v">{(totalDep / 1000).toFixed(1)}k</div>
            <div className="d">Trips that started here and were counted.</div>
          </div>
          <div className="card">
            <div className="k">Docks</div>
            <div className="v">{station.cap ?? "—"}</div>
            <div className="d">Capacity as the live feed currently reports it.</div>
          </div>
          <div className="card">
            <div className="k">Hours unusable</div>
            <div className="v" style={{ color: "var(--dim)" }}>—</div>
            <div className="d">
              Not yet published. Requires the coverage floor in §3 of the
              pre-registration.
            </div>
          </div>
          <div className="card">
            <div className="k">Estimated true demand</div>
            <div className="v" style={{ color: "var(--dim)" }}>—</div>
            <div className="d">
              Not yet published. Requires an estimator that has passed §4.
            </div>
          </div>
        </div>

        <div className="note">
          <strong>The two blank cards are the point of the project.</strong>{" "}
          Everything measurable from the trip archive alone is above them, and
          none of it can tell you how many people wanted a bike here and did not
          get one. That number is not small, it is not random, and it is not in
          any published dataset.
        </div>
      </section>

      <section>
        <p><a href="/">← the whole network</a></p>
      </section>
    </main>
  );
}
