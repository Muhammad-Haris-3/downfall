import fs from "node:fs";
import path from "node:path";
import DayShape from "@/components/DayShape";
import Reveal from "@/components/Reveal";

type Conditions = {
  window: [string, string];
  hours_matched: number;
  wet_threshold_mm: number;
  rain: { naive: number; stratified: number; lo: number; hi: number; cells: number; hours: number };
  temperature: { lo: number | null; hi: number | null; rel: number; hours: number }[];
  weekday_by_hour: number[];
  weekend_by_hour: number[];
};

export const metadata = {
  title: "Conditions — Downfall",
  description:
    "What weather and time of week do to ridership, and why the obvious calculation gets rain wrong.",
};

const load = (): Conditions =>
  JSON.parse(fs.readFileSync(path.join(process.cwd(), "public", "data", "conditions.json"), "utf8"));

const pct = (r: number) => `${((r - 1) * 100).toFixed(1)}%`;
const bandLabel = (b: { lo: number | null; hi: number | null }) =>
  b.lo === null ? "below 0" : b.hi === null ? "30+" : `${b.lo}–${b.hi}`;

export default function ConditionsPage() {
  const d = load();
  const gap = (d.rain.naive - d.rain.stratified) * 100;
  const maxRel = Math.max(...d.temperature.map((b) => b.rel));

  return (
    <>
      <section style={{ padding: "88px 32px 64px" }}>
        <Reveal>
          <div className="kicker">Conditions</div>
        </Reveal>
        <Reveal delay={0.06}>
          <h1 style={{ maxWidth: "17ch", marginBottom: 34 }}>
            Rain costs more than the <span style={{ color: "var(--accent)" }}>easy number</span> says.
          </h1>
        </Reveal>
        <Reveal delay={0.14}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(300px,1fr))", gap: 40, maxWidth: 960 }}>
            <p style={{ fontSize: 19, lineHeight: 1.5, color: "var(--muted)", margin: 0 }}>
              Every wet hour against every dry one says ridership falls{" "}
              <strong style={{ color: "var(--ink)" }}>{pct(d.rain.naive)}</strong>. Wet
              against dry within the same month and the same hour of the week says{" "}
              <strong style={{ color: "var(--accent)" }}>{pct(d.rain.stratified)}</strong>.
            </p>
            <p style={{ fontSize: 19, lineHeight: 1.5, color: "var(--muted)", margin: 0 }}>
              The easy number is too small by {gap.toFixed(1)} points — the
              opposite of the direction it was predicted to be wrong in.
            </p>
          </div>
        </Reveal>
      </section>

      <div className="rule" />

      <section>
        <div className="kicker">01 — The comparison</div>
        <h2 style={{ marginBottom: 30 }}>Why the easy number is wrong</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(280px,1fr))", gap: 20 }}>
          <div className="card">
            <div className="k">All hours, unadjusted</div>
            <div className="v">{pct(d.rain.naive)}</div>
            <div className="d">Every wet hour against every dry hour.</div>
          </div>
          <div className="card" style={{ borderColor: "var(--accent)" }}>
            <div className="k">Same month, same hour of week</div>
            <div className="v" style={{ color: "var(--accent)" }}>{pct(d.rain.stratified)}</div>
            <div className="d">
              95% interval {pct(d.rain.hi)} to {pct(d.rain.lo)}. {d.rain.cells.toLocaleString()} comparable
              cells, {d.rain.hours.toLocaleString()} hours.
            </div>
          </div>
        </div>

        <div className="note" style={{ marginTop: 26 }}>
          <strong>The prediction was wrong, and it stays on the record.</strong>{" "}
          Rain falls as readily at 3am as at 6pm, so wet hours ought to be
          over-represented among quiet ones and the rough number ought to
          overstate the effect. It understates it. New York&rsquo;s rain is
          disproportionately summer rain, and summer carries roughly four times
          the ridership of winter.
          <br /><br />
          The lesson is not &ldquo;control for confounders&rdquo;. It is that{" "}
          <strong>the direction a confounder pushes is not reliably guessable</strong>,
          so a rough number cannot be treated as a conservative one.
        </div>
      </section>

      <div className="rule" />

      <section>
        <div className="kicker">02 — Temperature</div>
        <h2 style={{ marginBottom: 14 }}>Temperature turns back down</h2>
        <p style={{ fontSize: 15.5, color: "var(--muted)", maxWidth: "72ch", marginTop: 0, marginBottom: 32 }}>
          Dry hours only, so the cold effect is not partly a rain effect, and
          relative to each hour-of-week&rsquo;s own average, so the shape of the
          day is already removed.
        </p>

        <div style={{ display: "grid", gridTemplateColumns: `repeat(${d.temperature.length},1fr)`, gap: 10, alignItems: "end", height: 280 }}>
          {d.temperature.map((b) => {
            const isPeak = b.rel === maxRel;
            return (
              <div key={bandLabel(b)} style={{ display: "flex", flexDirection: "column", justifyContent: "flex-end", height: "100%" }}>
                <div className="num" style={{ fontSize: 13, fontWeight: 700, marginBottom: 6, color: isPeak ? "var(--accent)" : "var(--muted)" }}>
                  {b.rel.toFixed(2)}×
                </div>
                <div style={{
                  height: `${(b.rel / maxRel) * 100}%`,
                  background: isPeak ? "var(--accent)" : "var(--dim)",
                  opacity: isPeak ? 1 : 0.45,
                  transition: "filter .25s ease",
                }} />
              </div>
            );
          })}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: `repeat(${d.temperature.length},1fr)`, gap: 10, marginTop: 10, borderTop: "2px solid var(--divider)", paddingTop: 10 }}>
          {d.temperature.map((b) => (
            <div key={bandLabel(b)} style={{ fontSize: 11.5, color: "var(--dim)", textAlign: "center" }}>{bandLabel(b)} °C</div>
          ))}
        </div>

        <p style={{ fontSize: 15.5, color: "var(--muted)", maxWidth: "72ch", marginTop: 26 }}>
          Freezing weather more than halves ridership, the peak sits at
          20–25&thinsp;°C, and above 30&thinsp;°C it falls again.{" "}
          <strong style={{ color: "var(--ink)" }}>A model that assumes demand rises
          with temperature is wrong at both ends.</strong>
        </p>
      </section>

      <div className="rule" />

      <section>
        <div className="kicker">03 — The week</div>
        <h2 style={{ marginBottom: 14 }}>Weekday and weekend are different shapes</h2>
        <p style={{ fontSize: 15.5, color: "var(--muted)", maxWidth: "72ch", marginTop: 0, marginBottom: 30 }}>
          Average departures across the network by local hour. Two commuting
          peaks against one afternoon peak — and the check that the timezone
          conversion is right.
        </p>
        <DayShape weekday={d.weekday_by_hour} weekend={d.weekend_by_hour} />

        <div className="note" style={{ marginTop: 30 }}>
          Everything here is built on departures <em>recorded</em> — the quantity
          this project argues understates demand wherever a station ran out.
          These are effects on recorded trips, not on demand. They are still
          worth having: they move the whole network at once, which is exactly
          what a per-station analysis has to hold constant.
        </div>

        <p style={{ fontSize: 13, color: "var(--dim)", marginTop: 22 }}>
          {d.hours_matched.toLocaleString()} network-hours. Weather: Open-Meteo
          archive, hourly, one point in Midtown — rain in the Bronx is not rain
          in Brooklyn, and that simplification is real. Wet means at least{" "}
          {d.wet_threshold_mm} mm in the hour.
        </p>
      </section>
    </>
  );
}
