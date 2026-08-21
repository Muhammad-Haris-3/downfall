import fs from "node:fs";
import path from "node:path";
import TempCurve from "@/components/TempCurve";
import DayShape from "@/components/DayShape";

type Conditions = {
  window: [string, string];
  hours_matched: number;
  wet_threshold_mm: number;
  rain: {
    naive: number; stratified: number; lo: number; hi: number;
    cells: number; hours: number;
  };
  temperature: { lo: number | null; hi: number | null; rel: number; hours: number }[];
  weekday_by_hour: number[];
  weekend_by_hour: number[];
};

export const metadata = {
  title: "Conditions — Downfall",
  description: "What weather and time of week do to ridership, and why the obvious calculation gets rain wrong.",
};

function load(): Conditions {
  return JSON.parse(
    fs.readFileSync(path.join(process.cwd(), "public", "data", "conditions.json"), "utf8"),
  );
}

const pct = (r: number) => `${((r - 1) * 100).toFixed(1)}%`;

export default function ConditionsPage() {
  const d = load();
  const gap = (d.rain.naive - d.rain.stratified) * 100;

  return (
    <main className="wrap">
      <div className="hero" style={{ paddingBottom: 20 }}>
        <h1>Rain costs more than the obvious calculation says.</h1>
        <p className="lede">
          Comparing every wet hour against every dry one says ridership falls{" "}
          <strong>{pct(d.rain.naive)}</strong>. Comparing wet and dry hours from
          the same month and the same hour of the week says{" "}
          <strong>{pct(d.rain.stratified)}</strong>.
        </p>
        <p className="lede">
          The easy number is too small by {gap.toFixed(1)} points — and that is
          the opposite of the direction it was expected to be wrong in.
        </p>
      </div>

      <section style={{ paddingTop: 24 }}>
        <h2>Why the easy number is wrong</h2>
        <p className="sub">
          Rain is not randomly assigned across the year. Neither is ridership.
        </p>
        <div className="grid">
          <div className="card">
            <div className="k">All hours, unadjusted</div>
            <div className="v">{pct(d.rain.naive)}</div>
            <div className="d">Every wet hour against every dry hour.</div>
          </div>
          <div className="card" style={{ borderColor: "var(--accent)" }}>
            <div className="k">Same month, same hour of week</div>
            <div className="v">{pct(d.rain.stratified)}</div>
            <div className="d">
              95% interval {pct(d.rain.hi)} to {pct(d.rain.lo)}. {d.rain.cells.toLocaleString()} comparable
              cells, {d.rain.hours.toLocaleString()} hours.
            </div>
          </div>
        </div>

        <div className="note">
          <strong>The prediction was wrong, and it is on the record.</strong>{" "}
          This was written expecting the naive figure to <em>overstate</em> the
          effect — rain falls as readily at 3am as at 6pm, so wet hours ought to
          be over-represented among quiet ones. The measurement says the reverse.
          New York&rsquo;s rain is disproportionately summer rain, and summer
          carries about four times the ridership of winter, so wet hours are
          drawn from the busy end of the year and are flattered by it.
          <br /><br />
          The lesson is not &ldquo;control for confounders&rdquo; — everyone says
          that. It is that <strong>the direction a confounder pushes is not
          reliably guessable</strong>, so a rough number cannot be treated as a
          conservative one just because it feels as though it should be.
        </div>
      </section>

      <section>
        <h2>Temperature</h2>
        <p className="sub">
          Measured on dry hours only, so the cold effect is not partly a rain
          effect, and expressed relative to that same hour-of-week&rsquo;s own
          average, so the shape of the day is already removed.
        </p>
        <TempCurve bands={d.temperature} />
        <div className="note">
          <strong>The curve turns back down.</strong> Freezing weather more than
          halves ridership, the peak sits at 20–25&thinsp;°C, and above
          30&thinsp;°C it falls again. A model that assumes demand rises with
          temperature is wrong at both ends of the range.
        </div>
      </section>

      <section>
        <h2>Weekday and weekend are different shapes, not different sizes</h2>
        <p className="sub">
          Average departures across the network, by local hour.
        </p>
        <DayShape weekday={d.weekday_by_hour} weekend={d.weekend_by_hour} />
        <p style={{ color: "var(--muted)", maxWidth: "68ch" }}>
          Weekdays carry two peaks, at roughly 08:00 and 17:00 — people going to
          work and coming back. Weekends carry one, in the middle of the
          afternoon. This is also the check that the time-zone conversion is
          right: an error of a few hours would have put the morning peak in the
          middle of the night.
        </p>
      </section>

      <section>
        <h2>What these numbers are, and are not</h2>
        <div className="note">
          Everything here is built on <strong>departures recorded</strong> — the
          quantity this project argues understates demand wherever a station ran
          out. So these are effects on recorded trips, not on demand. They are
          still worth having: they describe conditions that move the whole
          network at once, which is exactly what a per-station censoring analysis
          has to be able to hold constant.
        </div>
        <p style={{ color: "var(--dim)", fontSize: 14 }}>
          {d.hours_matched.toLocaleString()} network-hours,{" "}
          {d.window[0].slice(0, 4)}-{d.window[0].slice(4)} to{" "}
          {d.window[1].slice(0, 4)}-{d.window[1].slice(4)}. Weather: Open-Meteo
          archive, hourly, one point in Midtown — rain in the Bronx is not rain
          in Brooklyn, and that simplification is real. Wet means at least{" "}
          {d.wet_threshold_mm} mm in the hour.
        </p>
      </section>
    </main>
  );
}
