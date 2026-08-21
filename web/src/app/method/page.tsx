export const metadata = {
  title: "Method — Downfall",
  description:
    "How the record is kept honest, what has been established, and what has not.",
};

export default function Method() {
  return (
    <main className="wrap">
      <div className="hero" style={{ paddingBottom: 20 }}>
        <h1>How this is kept honest</h1>
        <p className="lede">
          The claim is about a quantity nobody measured. That makes the method
          the whole argument, so it is written down before the results and
          published whether or not it flatters them.
        </p>
      </div>

      <section style={{ paddingTop: 24 }}>
        <h2>Six mechanisms</h2>
        <p className="sub">
          Each prevents a specific way this record could quietly become wrong.
        </p>
        <div className="scroll">
          <table>
            <thead>
              <tr><th>Mechanism</th><th>What it prevents</th></tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>Append-only by construction</strong><br />
                  <span style={{ color: "var(--muted)" }}>Two events — open and close — appended, never edited. An outage is the pair.</span></td>
                <td>A store where “append-only” is a promise made by careful code rather than a property of the file.</td>
              </tr>
              <tr>
                <td><strong>Public git history as the audit trail</strong></td>
                <td>Silent retrospective editing. A change to a past line is a diff in a public commit.</td>
              </tr>
              <tr>
                <td><strong>Coverage recorded per run</strong></td>
                <td>A gap in collection reading as an hour in which no station ever ran out.</td>
              </tr>
              <tr>
                <td><strong>Unobserved boundaries flagged, never guessed</strong></td>
                <td>The most tempting error here: stamping an outage we did not see begin or end with a plausible time, and inheriting a duration that was never measured.</td>
              </tr>
              <tr>
                <td><strong>Kaplan–Meier, not means</strong></td>
                <td>Discarding outages still running when observation stopped. They are disproportionately the long ones, and dropping them roughly halves the answer.</td>
              </tr>
              <tr>
                <td><strong>Thresholds fixed before the estimator existed</strong></td>
                <td>Choosing what counts as success after seeing which method won.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2>Two checks that could have failed and did not</h2>
        <p className="sub">
          Neither is a claim about the world. Both reproduce an answer that was
          known in advance, which is the only way to test a pipeline.
        </p>

        <h3 style={{ fontSize: 17, margin: "18px 0 6px" }}>The clock</h3>
        <p style={{ color: "var(--muted)", maxWidth: "68ch" }}>
          Trip times are naive local; the availability feed publishes UTC.
          Mixing them misaligns every join by four or five hours and leaves
          nothing that looks wrong. After conversion, weekday departures peak at{" "}
          <strong>08:00</strong> and <strong>17:00</strong> and bottom out at{" "}
          <strong>03:00</strong>; weekends peak once, at <strong>14:00</strong>.
          That is commuting, and then leisure. An error of a few hours would have
          put the morning peak in the middle of the night.
        </p>

        <h3 style={{ fontSize: 17, margin: "18px 0 6px" }}>Daylight saving</h3>
        <p style={{ color: "var(--muted)", maxWidth: "68ch" }}>
          Rows dropped for an unresolvable clock time appear in{" "}
          <strong>November and nowhere else</strong> — 4,124 of them — and
          notably not in March. Fall-back repeats an hour, so 01:30 that Sunday
          happens twice and a naive timestamp cannot say which. Spring-forward
          skips an hour, so 02:30 never occurs and there is nothing to drop. A
          time-zone bug would not respect that distinction.
        </p>
      </section>

      <section>
        <h2>What is not established</h2>
        <div className="note">
          <strong>No demand estimate exists and no station has been ranked.</strong>{" "}
          Nothing on this site describes any station as under-served, because the
          coverage floor has not been met and the estimator has not been
          validated. Both thresholds were set before the data existed.
        </div>
        <ul style={{ color: "var(--muted)", maxWidth: "68ch", lineHeight: 1.8 }}>
          <li><strong>One city.</strong> Everything here is New York and generalises to nobody.</li>
          <li><strong>Demand is not desire.</strong> What can be recovered is how many people would have taken a bike from a stocked dock. Someone who checked an app, saw an empty station and stayed home is in no dataset and never will be.</li>
          <li><strong>A counterfactual is not a measurement.</strong> Any future figure of the form “this plan would have served N more trips” describes a world nobody ran, and will be published beside the simulator’s fidelity on the policy that actually happened.</li>
          <li><strong>Coverage will not reach 100%.</strong> The scheduler is best-effort and skips runs under load. That is recorded rather than worked around, and gaps disqualify the outages that span them.</li>
        </ul>
      </section>

      <section>
        <h2>Read the record</h2>
        <p style={{ color: "var(--muted)" }}>
          <a href="https://github.com/Muhammad-Haris-3/downfall/blob/main/PREREGISTRATION.md">Pre-registration</a>{" "}
          — thresholds, fixed before the estimator. Its §1 states what had
          already been seen when it was written.<br />
          <a href="https://github.com/Muhammad-Haris-3/downfall/blob/main/FINDINGS.md">Findings</a>{" "}
          — every measured result, in the order it was established, including
          the ones that went wrong.<br />
          <a href="https://github.com/Muhammad-Haris-3/downfall/blob/main/Downfall_SRS_v1.0.md">Requirements</a>{" "}
          — the specification, its rejected alternatives, and the kill criterion.
        </p>
      </section>
    </main>
  );
}
