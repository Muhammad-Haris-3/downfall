import fs from "node:fs";
import path from "node:path";
import type { Station } from "@/components/NetworkExplorer";
import StationPanel from "@/components/StationPanel";

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
 * Pages for the top-200 cohort only.
 *
 * Not a performance compromise. That cohort is the population the kill
 * criterion is evaluated on, fixed from the twelve months preceding collection
 * so it cannot be influenced by the outages being measured. A page for every
 * station would imply all 2,391 are part of the analysis.
 *
 * The route renders the same panel the map opens, embedded rather than modal -
 * so a shared link lands on exactly what the reader would have seen in context.
 */
export function generateStaticParams() {
  const { net } = load();
  return net.network.filter((s) => s.top200).map((s) => ({ id: s.s }));
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
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

export default async function StationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { net, profiles } = load();
  const station = net.network.find((s) => s.s === decodeURIComponent(id));
  if (!station) {
    return <section><h1>Unknown station</h1><p><a href="/">← the whole network</a></p></section>;
  }

  return (
    <>
      <section style={{ paddingBottom: 0 }}>
        <div className="kicker">Station</div>
        <StationPanel station={station} profile={profiles[station.s]} embedded />
      </section>
      <div className="rule" />
      <section>
        <a className="btn btn-ghost" href="/">← the whole network</a>
      </section>
    </>
  );
}
