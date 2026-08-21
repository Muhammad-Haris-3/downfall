# Downfall — Software Requirements Specification v1.0

**Project:** Downfall — measuring the demand that was never recorded
**Author:** Muhammad Haris Khokhar
**Date:** 2026-08-21
**Status:** Approved for M1 (M0 complete)

---

## 1. Introduction

### 1.1 Purpose

A bike-share station with no bikes records no trips. The people who arrived,
found an empty dock and walked away leave no trace in any dataset, because the
only event the system can record is a trip that happened.

So the stations that fail most often look, in the data, like the stations nobody
wants. **The measurement produces the conclusion, and the conclusion produces the
next failure.**

Downfall records when every station in New York's bike share becomes unusable and
when it recovers, estimates the demand censored by those periods, and tests
whether correcting for it changes which stations an operator would identify as
under-served. It then turns that corrected picture into a nightly rebalancing
plan and scores it.

### 1.2 What makes this different from the previous projects

In **Bellwether** and **GridCast** the author is the forecaster: a model predicts
and the system grades itself. In **Headway** the author is the referee: someone
else's published predictions are scored. In **Groundtruth** an estimate is marked
against a randomised trial that already knew the answer.

**Downfall's subject is data that does not exist.** Nothing published records the
rider who found an empty dock. The quantity of interest was never observed by
anyone, which is precisely why it is absent from the analyses that use this
dataset — and there are many.

Two further departures:

- **It ends in a decision, not a measurement.** Every previous project stops at
  *how wrong was it*. This one continues to *so do this, and here is what it is
  worth in trips served*. That is a stronger claim and carries a weaker warrant,
  and §9.4 states exactly how much weaker.
- **The central claim is checkable against cases with a known answer.** Stations
  that never run out have observed demand equal to true demand. The estimator can
  be marked against them, which is what separates this from asserting a hidden
  number and asking to be believed.

### 1.3 Scope

**In scope:** continuous observation of station availability; an append-only
record of outages; aggregation of the public trip archive to per-station demand;
estimation of censored demand; validation of that estimator against
never-stockout stations; a ranking test; a capacity-constrained rebalancing plan;
a replay simulator; a decision memo; and a public application of seven surfaces
specified in §6.5 — a network map, station pages, a nightly plan, a policy
simulator, a scored prediction register, a conditions view, and an evidence page.

**Declared extensions**, specified in §6.6 and out of scope until M7: service
equity by neighbourhood, a second city, and discharged e-bikes as a separate
scarcity. They are written down now so that they are extensions of a stated plan
rather than discoveries made when the project needed more to say.

**Out of scope:** predicting individual trips; any claim about another city until
one is added; advice to riders about specific journeys; real-time operations;
anything requiring paid infrastructure; any claim about people who consulted an
app and never left home.

### 1.4 Definitions

| Term | Meaning |
|---|---|
| **Outage** | A continuous period in which a station is unusable, of one of three kinds |
| **Empty** | No bikes available. A rider cannot take one |
| **Full** | No docks available. A rider cannot return one |
| **Offline** | Station not installed or not renting. Absent, which is not the same as empty |
| **Censored hour** | A station-hour containing outage minutes, during which observed departures understate demand |
| **Observed demand** | Departures recorded in the trip archive. What every existing analysis uses |
| **True demand** | Departures that would have occurred had a bike been available throughout |
| **Unconstraining** | Estimating true demand from a censored series |
| **Never-stockout station** | A station with zero recorded empty minutes over the window. Its observed demand *is* its true demand, so it serves as held-out truth |
| **Publish cycle** | The 70s interval at which the feed regenerates. The finest interval in which an outage can be observed |
| **Handover** | The gap between one collection job ending and the next starting |
| **Coverage** | Share of wall-clock time during which collection was actually running |

### 1.5 Intended audience

Hiring managers and technical reviewers primarily. Sections 2, 3 and the decision
memo are written for a reader with no statistical background. Sections 6 onward
are written so that an independent party can reproduce every number.

---

## 2. Business context and problem statement

### 2.1 Context

New York's bike share has around 2,500 stations and carries over a million trips
a month. At the moment of writing, **473 of those stations — 19% of the network —
were unusable**: 176 with no bikes, 297 with no free docks.

Operators move bikes overnight to correct this, at real cost, and the decision of
where to move them is made from trip counts. Trip counts are the one thing
guaranteed to be wrong in exactly the situation the decision is meant to fix.

The dataset is among the most analysed open datasets in existence. Essentially
every published analysis of it treats departures as demand.

### 2.2 Problem statement

> Demand is measured by counting trips, and a trip cannot be counted at a station
> that had nothing to take. The stations that fail most are therefore recorded as
> the stations that are wanted least, and resourced accordingly.

### 2.3 Primary questions

| # | Question | Method |
|---|---|---|
| BQ-1 | How much of the network's demand is censored, and where? | Outage minutes joined to station-hours |
| BQ-2 | **Can hidden demand be recovered on cases where the answer is known?** | Synthetic censoring of never-stockout stations, §9.2 |
| BQ-3 | Does correcting for censoring change which stations rank as under-served? | Rank-change against censored exposure, §9.3 |
| BQ-4 | Is the failure asymmetric — is finding a dock harder than finding a bike? | Outage counts and durations by kind, across a full week |
| BQ-5 | What would a corrected demand picture change about tonight's rebalancing? | Constrained assignment, replayed, §9.4 |

BQ-2 is the load-bearing one. If it fails, BQ-3 and BQ-5 cannot be asked, and the
project reports BQ-1 and BQ-4 with an account of why the correction did not work.

### 2.4 Success criteria

| # | Criterion | Threshold |
|---|---|---|
| SC-1 | Coverage in steady state | ≥ 95% of wall-clock, published continuously, not assumed |
| SC-2 | **Observation floor materially finer than what is measured** | Publish cycle 70s against a median outage of ~10 min — established in M0 |
| SC-3 | Append-only record | Events cannot be altered after writing; a property of the store and of public git history, not of careful code |
| SC-4 | **Estimator validated against known answers** | Pre-registered thresholds in `PREREGISTRATION.md` §4, set before the estimator existed |
| SC-5 | Every unobserved boundary flagged | No duration is ever inferred for an outage whose start or end fell in a gap |
| SC-6 | Cost | Zero. Free tiers only |
| SC-7 | Legibility | A non-technical reader can state the finding from the memo alone |

---

## 3. Feasibility study

Established in M0 and recorded in `FINDINGS.md`. Every figure below is measured.

| Question | Answer | Where |
|---|---|---|
| Can outages be observed at all? | Yes. Feed republishes every **70s**, exactly, nine gaps with no variance | M0-T1 |
| How stale is a reading? | **~122s** at read time, systematically late, not noisily late | M0-T1 |
| How long is an outage? | Median **9.9 min** empty, **13.8 min** full (evening peak, Kaplan–Meier) | M0-T6 |
| Is the observation floor fine enough? | Yes. Only **0.4%** of outages are shorter than one publish cycle | M0-T6 |
| Can demand be joined to availability? | Yes. **98.07%** of 1.2M February trips join on `short_name` | M0-T4 |
| Does the history fit a free tier? | Yes. A month aggregates 237 MB → **1.9 MB**; all 31 months ≈ **59 MB** | M0-T5 |
| Is there enough failure to be worth studying? | 473 of 2,508 stations unusable at a single observed moment | M0-T3 |

### 3.1 Principal risk to validity: the estimator cannot be checked

The claim "true demand at this station was 74, not 31" is unfalsifiable in the
general case. Nobody counted the people who walked away.

**Mitigation, and the reason the project is viable:** some stations never run out,
so for them observed demand *is* true demand. Synthetic censoring can be imposed
on those, the estimator run, and the recovered figure compared against a number
that was on the table the whole time. The pass thresholds are fixed in
`PREREGISTRATION.md` §4 and were written before any estimator existed.

**If it fails, the central claim is withdrawn rather than caveated.**

### 3.2 Second risk: never-stockout stations are not a random sample

A station that never runs out differs from one that does — likely quieter, better
capitalised, or better balanced. Validating on the first and applying to the
second is an extrapolation, not an interpolation.

**Mitigation:** synthetic censoring is drawn from the observed outage pattern of a
station matched on capacity and total departures — matched on variables the
estimator does not itself use. Residual extrapolation is reported as a limit of
the result, not solved.

### 3.3 Third risk: demand is not desire

What can be recovered is *departures that would have occurred from a stocked
dock*. A person who opened the app, saw an empty station and stayed home is
invisible to every method here and always will be.

**Mitigation:** none is possible. The quantity is named precisely wherever it
appears, and no figure is described as "demand" without qualification.

### 3.4 Fourth risk: this describes one city

Everything is New York. Whether the correction matters elsewhere is unknown.
Adding a second system is a declared milestone (M7), not a claim made in advance.

---

## 4. SDLC methodology

Incremental, milestone-gated, with each milestone answering one question that
could kill or redirect the project. M0 established that the data supports the
question at all; it produced two design-changing defects, both recorded.

### 4.1 Definition of Done (applies to every milestone)

1. The question the milestone existed to answer is answered with a number.
2. Every figure quoted is reproducible from committed code and committed data.
3. Anything not established is stated as not established, in the same document.
4. Tests exist for the guarantees, not only for the plumbing.
5. Findings are committed before the next milestone begins.

### 4.2 Collection starts before the application

Availability data cannot be back-filled. An hour not collected is gone. The
collector therefore shipped in M0, before any analysis or interface existed, and
runs continuously from that point.

---

## 5. Data source specification

| Source | Access | Verified | Use |
|---|---|---|---|
| **GBFS `station_status`** | Keyless, public, `ttl: 60` | 2026-08-20 | Live availability. The only source for outages |
| **GBFS `station_information`** | Keyless, public | 2026-08-20 | Station name, `short_name`, position, capacity |
| **Citi Bike trip archive** | Public S3, no credentials | 2026-08-20 | Historical demand. 31 monthly files 2024-01 → 2026-07, plus yearly archives to 2013 |
| **Open-Meteo** | Keyless | 2026-08-20 | Weather covariates (M3+) |

### 5.1 Characteristics requiring handling

| Characteristic | Consequence | Handling |
|---|---|---|
| Feed republishes every 70s | Polling faster returns an identical file | Poll at 60s, the declared `ttl`. Slower than publication, so no file is skipped |
| Readings ~122s stale | Point-in-time claims are only good to ±2 min | Durations used freely; no boundary drawn finer than two minutes |
| **87 stations report `last_reported` = 86400** | 1970 placeholder | Excluded from all timing work by threshold, not by hand |
| **53 stations report `capacity = 0`** | Permanently report zero bikes | Would read as a permanent stockout. Must never be pooled with real outages |
| `station_id` is 1,812 UUIDs and 696 numeric strings | Does not appear in the trip archive at all | Join on `short_name`; identity is dated, since ids are reissued on rename |
| Trip times are naive **local**, feed is **UTC** | Misalignment of 4–5 hours that looks entirely normal | Converted once, at ingest; validated by recovering the commute peak |
| DST transitions | Two impossible or doubled clock hours a year | Dropped and counted, never shifted. A shifted timestamp is a fabricated one |
| **`2026-04` is a third the size of its neighbours** | Month-over-month figures spanning April are suspect | Flagged; no analysis may average across it until resolved |
| 0.09% of trips carry no start station | Small but non-random | Excluded from departures, counted and reported |
| GitHub's scheduler is best-effort | Coverage will not reach 100% | Not worked around, because it cannot be. Recorded per run; gaps disqualify the outages spanning them |

---

## 6. Functional requirements

### 6.1 Collection and the record

| # | Requirement |
|---|---|
| **FR-1** | Poll `station_status` at an interval no faster than the declared `ttl` and no slower than the publish cycle |
| **FR-2** | Classify each station as empty, full, offline, or usable, with **offline taking precedence** — a switched-off station reporting zero bikes must never be recorded as a stockout |
| **FR-3** | Append an `open` event when a station enters an unusable state, and a `close` event when it leaves. **Never modify a written event** |
| **FR-4** | Timestamp events from the feed's own `last_reported`, never from local wall clock |
| **FR-5** | File events by the day they were **observed**, never by the timestamp they carry |
| **FR-6** | Flag any outage already underway when observation began, or beginning after a gap longer than the handover threshold, as having an unobserved start |
| **FR-7** | Flag any outage that ended during a gap as having an unobserved end |
| **FR-8** | Record per-run coverage: window, files seen, requests, failures, and suspected skipped files |
| **FR-9** | Detect and report publication intervals longer than expected, which would indicate a skipped file |
| **FR-10** | Carry open outages across job boundaries through durable state, resolved against the first file of the next run |

### 6.2 Demand aggregation

| # | Requirement |
|---|---|
| **FR-11** | Aggregate the trip archive to departures and arrivals per station per UTC hour |
| **FR-12** | Count departures and arrivals **independently** — a trip with an unusable end still proves a bike left |
| **FR-13** | Convert local trip timestamps to UTC once, dropping and counting impossible clock times rather than shifting them |
| **FR-14** | Emit a manifest per mart recording row counts, every category of dropped row, and the span produced |
| **FR-15** | Join trips to stations on `short_name`, dated, recording the match rate achieved |

### 6.3 Estimation and validation

| # | Requirement |
|---|---|
| **FR-16** | Identify censored station-hours by intersecting outage intervals with station-hours |
| **FR-17** | Estimate true demand for censored station-hours |
| **FR-18** | **Validate the estimator against never-stockout stations under synthetic censoring**, reporting both absolute and signed error |
| **FR-19** | Report the ranking test of §9.3 with an effect size, not only a p-value |
| **FR-20** | Publish a refused result with the same prominence a positive one would receive |

### 6.4 Decision layer (M4+)

| # | Requirement |
|---|---|
| **FR-21** | Produce a rebalancing plan under an explicit crew and capacity budget |
| **FR-22** | Replay historical days under counterfactual policies, reporting trips served |
| **FR-23** | **Report simulator fidelity against the observed policy alongside every counterfactual it produces** |
| **FR-24** | Support alternative objectives — total trips served, and equality of service across areas — and report the trade-off as a number |

### 6.5 The application (M5–M6)

Seven surfaces. They are specified individually because "a public site" is not a
requirement — it is a placeholder that can be satisfied by anything, and this
project's findings are only worth as much as the reader's ability to check them.

Each surface answers a different question, and each names the reader it is for.

#### 6.5.1 The map — *where is the problem?*

| # | Requirement |
|---|---|
| **FR-25** | Render every station in the network at its position, on one view of the city |
| **FR-26** | Colour each station by its **failure rate**, not by its current state. A snapshot is weather; the rate is climate, and the rate is what an operator can act on |
| **FR-27** | Three legible bands — reliable / intermittent / chronic — with the thresholds stated on the page rather than chosen for visual balance |
| **FR-28** | Support filtering to `empty` and `full` separately, since they are different failures with different fixes (§6.3, FR-16) |
| **FR-29** | Show observation coverage for the displayed window, so a pale area is never mistaken for a healthy one |

**Reader:** anyone, in ten seconds. This is the surface that has to work before any
other one is worth building.

#### 6.5.2 Station pages — *what happens here, and what was never recorded?*

| # | Requirement |
|---|---|
| **FR-30** | Per station: departures and arrivals by hour, hours unusable, and capacity |
| **FR-31** | **Observed demand and estimated true demand on the same axes**, with the gap named. This is the project's central claim, made concrete for one place a reader may know |
| **FR-32** | The estimate's uncertainty shown, never a bare point |
| **FR-33** | Hour-of-week profile: which day and which hour this station fails |
| **FR-34** | The station's own record of excluded outages — unobserved boundaries, low-coverage hours — on the page, not in a footnote |

**Reader:** an operator, or a rider who knows the corner. A number about a place
someone recognises is checkable in a way a network average is not.

#### 6.5.3 Tonight's plan — *so what should be done?*

| # | Requirement |
|---|---|
| **FR-35** | Produce a per-vehicle route: which stations, in what order, how many bikes moved at each |
| **FR-36** | State the expected gain **in trips served**, not in any modelling metric. An operator is not paid in RMSE |
| **FR-37** | Show the same plan under the naive demand ranking beside it, so the difference the correction makes is the visible quantity |
| **FR-38** | Carry the simulator's measured fidelity (FR-23) on the same screen as the gain it is used to claim |

**Reader:** the person deciding where three trucks go. The only surface that ends
in an instruction.

#### 6.5.4 The simulator — *what if it were different?*

| # | Requirement |
|---|---|
| **FR-39** | Replay a real historical day under user-set conditions, returning trips served |
| **FR-40** | Controls for at minimum: crew size, shift start time, and objective (§6.4, FR-24) |
| **FR-41** | Present every result as a difference from the observed day, never as an absolute claim about a world nobody ran |
| **FR-42** | Refuse, visibly, to extrapolate beyond the conditions the simulator was validated on, rather than returning a confident number outside them |

**Reader:** a manager asking "could we do this with two trucks?" — and getting a
number instead of an opinion.

#### 6.5.5 The scoreboard — *were you right?*

| # | Requirement |
|---|---|
| **FR-43** | Publish, for a stated future window, which stations are predicted to fail — **written before the window begins** |
| **FR-44** | Score each prediction once its outcome exists, and never before |
| **FR-45** | Show the standing record: hit rate, miss rate, and the baseline of "the same stations as last week", which any useful method must beat |
| **FR-46** | Every published prediction remains visible after scoring, including the wrong ones. A register holding only its successes is an advertisement |

**Reader:** anyone deciding whether to believe the rest of the site. This is the
surface that makes the others credible.

#### 6.5.6 Conditions — *what moves demand?*

| # | Requirement |
|---|---|
| **FR-47** | Demand and failure rates by weather condition, temperature band, weekday/weekend, and public holiday |
| **FR-48** | Report these as *associations*, explicitly not as causal claims, except where a design supports the stronger reading |
| **FR-49** | Charts legible without a statistical background (SC-7) |

**Reader:** the general visitor. Also the honest answer to "isn't this all just
rain?", which is a fair question and deserves a page rather than a sentence.

#### 6.5.7 The evidence page — *why should this be believed?*

| # | Requirement |
|---|---|
| **FR-50** | Show the validation of `PREREGISTRATION.md` §4 in full: the never-stockout cohort, the synthetic censoring, recovered against known, and the thresholds that were set beforehand |
| **FR-51** | Show it **whatever the result** — a failed validation is published on the same page with the same prominence (FR-20) |
| **FR-52** | Link every headline figure on the site back to the finding and the commit that produced it |

**Reader:** the sceptic, and the reviewer. Every other page asserts; this one is
the only page that argues.

#### 6.5.8 Across the whole application

| # | Requirement |
|---|---|
| **FR-53** | Coverage, and the count of outages excluded for unobserved boundaries, visible on every page that quotes a rate — not on an "about" page (NFR-5) |
| **FR-54** | Two-page decision memo readable with no technical background |
| **FR-55** | No figure appears before its pre-registered floor is met; the site reports progress toward the threshold instead of a provisional number captioned "early" |

### 6.6 Declared extensions (M7+)

Specified now so that they are extensions of a stated plan rather than
discoveries made when the project needed more to say. Each is out of scope for
M6 and none is assumed to work.

| # | Requirement | Why it is worth doing |
|---|---|---|
| **FR-56** | **Service equity.** Failure rates and censored demand by neighbourhood income and density, using public census geography | Rebalancing that maximises trips served concentrates bikes where trips already are. Whether that leaves particular areas systematically worse served is measurable, and the trade-off against total trips is a number the simulator can produce |
| **FR-57** | **A second city.** Repeat the pipeline on another system with a public GBFS feed and trip archive | Every result here is New York's until this runs. It is the only requirement that addresses §3.4, and the correction either transfers or it does not — both are findings |
| **FR-58** | **Electric bikes as separate scarcity.** Treat a discharged e-bike as unavailable stock even when physically present | A dock with bikes nobody can ride is a stockout the current classification cannot see. It would appear in the data as a healthy station with unexplained low demand — the same failure mode as the main project, one level down |

**FR-58 is the most interesting of the three** precisely because it is the same
error again: stock that exists, cannot be used, and therefore records no demand.
If the method works at all, it should work there too, and that is a test of the
method rather than an extension of it.

---

## 7. Non-functional requirements

| # | Requirement |
|---|---|
| **NFR-1** | Zero cost. Free tiers only, no card, no paid service |
| **NFR-2** | The collector depends on the standard library alone. A dependency it does not have cannot break it at 3am |
| **NFR-3** | Collection runs unattended, without the author's machine |
| **NFR-4** | Two collectors must never run concurrently |
| **NFR-5** | **A gap in collection must be visible as a gap**, never readable as a period in which nothing happened |
| **NFR-6** | Every published figure reproducible from committed code and committed data |
| **NFR-7** | The event log must be verifiable as append-only by a reader with access to neither the author nor the machine |
| **NFR-8** | Poll no faster than the publisher's declared `ttl` |
| **NFR-9** | Storage within a 500 MB free tier for at least twelve months, with a declared retention policy before that expires |
| **NFR-10** | A killed job must not leave a corrupt state file |
| **NFR-11** | Tests cover the honesty guarantees, and each states why it exists |
| **NFR-12** | Constants that appear in the pre-registration are asserted against that document by the test suite |

---

## 8. Architecture

```
GBFS station_status / station_information      Citi Bike trip archive     Open-Meteo
   keyless, ttl 60, republished every 70s        29 GB, public S3          keyless
              |                                          |                     |
              v                                          v                     v
    GitHub Actions - hourly job                GitHub Actions - bulk aggregation
    collecting 59 of every 60 min              (runner sits next to the bucket)
              |                                          |
              v                                          v
    data/events/YYYY-MM-DD.ndjson              data/marts/trip_counts_*.parquet
    append-only open/close events              per-station, per-UTC-hour
    data/runs.ndjson  coverage                 data/marts/manifest_*.json
              |                                          |
              +---------------------+--------------------+
                                    v
                     censored station-hours  ->  estimator
                                    v
                     validation against never-stockout stations
                                    v
                     ranking test  ->  rebalancing plan  ->  replay simulator
                                    v
                          Next.js site on Vercel
```

### 8.1 Decisions and rejected alternatives

| Decision | Rejected alternative | Why |
|---|---|---|
| **Event log, appended** | A row per outage, updated on recovery | An outage opens in one job and closes in a later one. Updating means rewriting history every hour, and "append-only" becomes a promise made by careful code rather than a property of the store |
| **Files in git** | Hosted Postgres | Collection could start the same day, with no account and no credential. Git history is itself the audit trail. Postgres is added when the application needs to query, not before |
| **Store outages, not snapshots** | A snapshot per station per cycle | 3.1M rows a day to answer no question that is asked. The outage interval is ~10,000× smaller and is the exact object the analysis consumes |
| **59 minutes of every 60** | 4½ minutes of every 5 | Same handover gap, 24 per day instead of 288. ~1.7% of the clock blind against ~10% |
| **Bulk aggregation in CI** | Downloading the archive locally | Measured 0.76 MB/s from a home connection: eight hours for the monthly files. The runner sits next to the bucket |
| **Poll at 60s** | Poll at 35s | The publisher declares `ttl: 60`. Faster polling buys nothing, because timestamps come from the feed's clock, not ours |

### 8.2 Free-tier constraints treated as design inputs

- Actions minutes are unlimited only on **public** repositories. 42,480 minutes a
  month are needed; 2,000 are free on private. The repository is public, and this
  is a requirement rather than a preference.
- 500 MB of database is roughly one year of outage rows at the prototype's row
  size. Integer identifiers and a Headway-style retention policy are scheduled
  before that binds, not after.
- The 29 GB archive is never copied to a laptop, because measurement said not to.

---

## 9. Analysis plan and statistical methods

### 9.1 Durations are censored, and are treated as such

Outages still open when observation stops are **right-censored**: known to have
lasted at least that long. Discarding them removes disproportionately the long
ones and roughly halves the estimate, so **Kaplan–Meier** is used rather than
means. Outages whose start or end fell in a gap carry no duration at all and are
excluded and counted.

### 9.2 The validation that decides the project

Fully specified in `PREREGISTRATION.md` §4, fixed before the estimator existed:
never-stockout stations, synthetic censoring drawn from a matched station,
estimate, compare. Pass requires median absolute error ≤ 20% **and** median
signed error within ±10%. The second condition exists because the entire claim
concerns a systematic direction, and a method biased in a consistent direction
would manufacture the finding.

### 9.3 The ranking test

Stations ranked by observed departures and by estimated true demand. The claim is
supported only if rank change is positively associated with censored exposure at
p < 0.01, one-sided, **with the effect size in rank positions per censored hour
reported as the finding**. A significant but negligible effect is a null result
and is described as one.

### 9.4 What the decision layer can and cannot claim

A counterfactual is not a measurement. "This plan would have served 8% more
trips" describes a world nobody ran, and no validation procedure can make it an
observation.

The only honest partial check is whether the simulator reproduces the **observed**
policy's outcomes on held-out days. That fidelity figure is published beside every
counterfactual derived from it, and the distinction is never blurred.

---

## 10. Milestone plan

| | Question | Gate |
|---|---|---|
| **M0** | Can outages be observed, and can trips be tied to stations? | ✅ Complete — 70s floor, 98.07% join, 9.9 min median |
| **M1** | How much demand is censored, and where? | Coverage floor of `PREREGISTRATION.md` §3 |
| **M2** | Can hidden demand be recovered where the answer is known? | Validation thresholds §4. **Kill gate** |
| **M3** | Does the correction change which stations rank as under-served? | Effect size §5 |
| **M4** | What should tonight's rebalancing do, and what is it worth? | Simulator fidelity reported first |
| **M5** | Published before the outcome, scored after | A public register with entries that predate their outcomes |
| **M6** | The seven surfaces of §6.5 | Legibility, SC-7. A reader can state the finding without help |
| **M7** | Is service equitable, and what does equity cost in trips? | The trade-off reported as a number, not an argument |
| **M8** | Does any of it hold in a second city? | Declared, not assumed. Addresses §3.4 |
| **M9** | Is a discharged e-bike an invisible stockout? | The same error one level down — a test of the method, not an extension |

---

## 11. Risks and mitigations

| # | Risk | Mitigation |
|---|---|---|
| R-1 | **Estimator cannot be validated** | §3.1. Pre-registered thresholds; withdrawal rather than caveat |
| R-2 | Never-stockout stations are unrepresentative | §3.2. Matched synthetic censoring; residual extrapolation reported |
| R-3 | Censoring turns out to be too rare to matter | Kill criterion §11.1 |
| R-4 | Coverage never reaches the floor | Published continuously; the project cannot quietly proceed without it |
| R-5 | Feed changes shape or access is withdrawn | Collected history remains usable; the event log is self-describing |
| R-6 | Zero-capacity or offline stations contaminate outage counts | Classification order, tested; 53 known stations tracked |
| R-7 | Counterfactual claims read as measurements | FR-23. Fidelity published alongside, always |
| R-8 | Storage exceeds the free tier in year two | NFR-9. Retention scheduled before it binds |

### 11.1 Kill criterion

Fixed in `PREREGISTRATION.md` §6, before any estimate existed. The project stops,
and publishes the negative result with full prominence, if **any** of:

- Fewer than **2%** of station-hours at the top-200 stations by departures are
  censored — there is nothing meaningful to recover regardless of method.
- Validation fails the thresholds of §4.
- The ranking does not move under §5.
- Coverage never reaches §3.

---

## 12. Acceptance criteria

| # | Criterion |
|---|---|
| **AC-1** | Collection runs unattended at ≥ 95% coverage, published |
| **AC-2** | Every outage with an unobserved boundary is flagged, and the count is public |
| **AC-3** | The event log is demonstrably append-only from public history alone |
| **AC-4** | Trip archive aggregated with a published match rate and a manifest per mart |
| **AC-5** | Estimator validated against never-stockout stations, or **withdrawn** |
| **AC-6** | The ranking test reported with an effect size, whichever way it comes out |
| **AC-7** | Every counterfactual accompanied by the simulator's fidelity on observed policy |
| **AC-8** | Predictions published before their outcomes and scored after, **including the wrong ones** |
| **AC-9** | All seven application surfaces of §6.5 delivered, each answering the question it names |
| **AC-10** | Coverage and exclusion counts visible on every page that quotes a rate, not on an "about" page |
| **AC-11** | A non-technical reader can state the finding from the memo alone |
| **AC-12** | Total cost zero |

---

## 13. Document control

| | |
|---|---|
| **Version** | 1.0 |
| **Date** | 2026-08-21 |
| **Status** | Approved for M1 |
| **Supersedes** | — |
| **Companion documents** | `PREREGISTRATION.md` (thresholds, fixed before the estimator), `FINDINGS.md` (measured results as established), `Downfall_Design_Phase_v1.0.md` (to follow at M1) |

Amendments follow the rule in `PREREGISTRATION.md` §8: a new numbered version,
committed separately, with the reason stated, and the previous version intact in
git history. **No amendment may weaken a validation threshold after the
corresponding analysis has been run.**
