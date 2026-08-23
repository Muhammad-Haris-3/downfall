import Reveal from "@/components/Reveal";

export const metadata = {
  title: "Method — Downfall",
  description: "How the record is kept honest, what has been established, and what has not.",
};

const MECHANISMS = [
  { n: "01", title: "Append-only by construction", body: "Two events — open and close — appended and never edited. An outage is the pair. Prevents a store where append-only is a promise made by careful code rather than a property of the file." },
  { n: "02", title: "Public git history as the audit trail", body: "Prevents silent retrospective editing. Any change to a past line is a diff in a public commit." },
  { n: "03", title: "Coverage recorded per run", body: "Prevents a gap in collection reading as an hour in which no station ever ran out." },
  { n: "04", title: "Unobserved boundaries flagged, never guessed", body: "The most tempting error here: stamping an outage we did not see begin or end with a plausible time, and inheriting a duration that was never measured." },
  { n: "05", title: "Kaplan–Meier, not means", body: "Prevents discarding outages still running when observation stopped. They are disproportionately the long ones, and dropping them roughly halves the answer." },
  { n: "06", title: "Thresholds fixed before the estimator existed", body: "Prevents choosing what counts as success after seeing which method won." },
];

const LIMITS = [
  { title: "One city", body: "Everything here is New York and generalises to nobody until a second system is added." },
  { title: "Demand is not desire", body: "What can be recovered is how many people would have taken a bike from a stocked dock. Someone who checked an app, saw an empty station and stayed home is in no dataset and never will be." },
  { title: "A counterfactual is not a measurement", body: "Any figure of the form “this plan would have served N more trips” describes a world nobody ran, and will be published beside the simulator's fidelity on the policy that actually happened." },
  { title: "Coverage will not reach 100%", body: "The scheduler is best-effort and skips runs under load. That is recorded rather than worked around, and gaps disqualify the outages that span them." },
];

export default function Method() {
  return (
    <>
      <section style={{ padding: "88px 32px 64px" }}>
        <Reveal><div className="kicker">Method</div></Reveal>
        <Reveal delay={0.06}>
          <h1 style={{ maxWidth: "15ch", marginBottom: 30 }}>
            The method is the <span style={{ color: "var(--accent)" }}>whole argument</span>.
          </h1>
        </Reveal>
        <Reveal delay={0.14}>
          <p style={{ fontSize: 19, lineHeight: 1.5, color: "var(--muted)", maxWidth: "62ch", margin: 0 }}>
            The claim is about a quantity nobody measured. So it is written down
            before the results, and published whether or not it flatters them.
          </p>
        </Reveal>
      </section>

      <div className="rule" />

      <section>
        <div className="kicker">01 — Mechanisms</div>
        <h2 style={{ marginBottom: 30 }}>Six mechanisms</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(320px,1fr))", gap: 0, borderTop: "2px solid var(--divider)", borderLeft: "2px solid var(--divider)" }}>
          {MECHANISMS.map((m) => (
            <div key={m.n} style={{ borderRight: "2px solid var(--divider)", borderBottom: "2px solid var(--divider)", padding: 26 }}>
              <div className="num" style={{ fontSize: 28, fontWeight: 800, color: "var(--accent)", letterSpacing: "-.04em", marginBottom: 10 }}>{m.n}</div>
              <h3 style={{ marginBottom: 10 }}>{m.title}</h3>
              <p style={{ fontSize: 14.5, color: "var(--muted)", margin: 0, lineHeight: 1.55 }}>{m.body}</p>
            </div>
          ))}
        </div>
      </section>

      <div className="rule" />

      <section>
        <div className="kicker">02 — Checks</div>
        <h2 style={{ marginBottom: 14 }}>Two checks that could have failed</h2>
        <p style={{ fontSize: 15.5, color: "var(--muted)", maxWidth: "72ch", marginTop: 0, marginBottom: 32 }}>
          Neither is a claim about the world. Both reproduce an answer that was
          known in advance, which is the only way to test a pipeline.
        </p>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(320px,1fr))", gap: 26 }}>
          <div>
            <h3 style={{ marginBottom: 10 }}>The clock</h3>
            <p style={{ fontSize: 15, color: "var(--muted)", lineHeight: 1.6 }}>
              Trip times are naive local; the availability feed publishes UTC.
              Mixing them misaligns every join by four or five hours and leaves
              nothing that looks wrong. After conversion, weekday departures peak
              at <strong style={{ color: "var(--ink)" }}>08:00</strong> and{" "}
              <strong style={{ color: "var(--ink)" }}>17:00</strong> and bottom out at{" "}
              <strong style={{ color: "var(--ink)" }}>03:00</strong>; weekends peak
              once, at 14:00. That is commuting, and then leisure. An error of a
              few hours would have put the morning peak in the middle of the night.
            </p>
          </div>
          <div>
            <h3 style={{ marginBottom: 10 }}>Daylight saving</h3>
            <p style={{ fontSize: 15, color: "var(--muted)", lineHeight: 1.6 }}>
              Rows dropped for an unresolvable clock time appear in{" "}
              <strong style={{ color: "var(--ink)" }}>November and nowhere else</strong>{" "}
              — 4,124 of them — and notably not in March. Fall-back repeats an
              hour, so 01:30 that Sunday happens twice and a naive timestamp
              cannot say which. Spring-forward skips an hour, so 02:30 never
              occurs and there is nothing to drop. A time-zone bug would not
              respect that distinction.
            </p>
          </div>
        </div>
      </section>

      <div className="rule" />

      <section>
        <div className="kicker">03 — Limits</div>
        <h2 style={{ marginBottom: 24 }}>What is not established</h2>

        <div className="note" style={{ marginBottom: 30 }}>
          <strong>No demand estimate exists and no station has been ranked.</strong>{" "}
          Nothing on this site describes any station as under-served, because the
          coverage floor has not been met and the estimator has not been
          validated. Both thresholds were set before the data existed.
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(280px,1fr))", gap: 20 }}>
          {LIMITS.map((l) => (
            <div key={l.title} className="card">
              <h3 style={{ marginBottom: 10 }}>{l.title}</h3>
              <p style={{ fontSize: 14.5, color: "var(--muted)", margin: 0, lineHeight: 1.55 }}>{l.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section style={{ background: "var(--accent)", color: "#fff", maxWidth: "none", padding: "80px 0", marginTop: 16 }}>
        <div className="wrap">
          <h2 style={{ fontSize: "clamp(28px,4vw,50px)", maxWidth: "22ch", marginBottom: 24 }}>
            Read the record, not the summary.
          </h2>
          <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
            <a className="btn" href="https://github.com/Muhammad-Haris-3/downfall/blob/main/PREREGISTRATION.md" style={{ background: "#fff", color: "var(--accent)" }}>Pre-registration</a>
            <a className="btn" href="https://github.com/Muhammad-Haris-3/downfall/blob/main/FINDINGS.md" style={{ background: "transparent", color: "#fff", border: "2px solid rgba(255,255,255,.5)" }}>Findings</a>
            <a className="btn" href="https://github.com/Muhammad-Haris-3/downfall/blob/main/Downfall_SRS_v1.0.md" style={{ background: "transparent", color: "#fff", border: "2px solid rgba(255,255,255,.5)" }}>Requirements</a>
          </div>
        </div>
      </section>
    </>
  );
}
