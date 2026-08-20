# Downfall — M1 Specification: how much demand is censored, and where?

**Milestone:** M1 — Censoring exposure
**Author:** Muhammad Haris Khokhar
**Date:** 2026-08-21
**Status:** Approved. **Written before M1 ran** — unlike M0, which had no spec (see `Downfall_M0_Summary.md` §1.1)
**Depends on:** `Downfall_SRS_v1.0.md`, `PREREGISTRATION.md`, M0 complete

---

## 1. The question

> **How much of this network's recorded demand is suppressed by unavailability,
> and is it concentrated or spread?**

M0 established that outages can be seen and that trips can be tied to stations.
M1 measures the size of the thing the project exists to correct.

This is deliberately a *descriptive* milestone. **No estimate of hidden demand is
produced here.** Recovering it is M2, and mixing the two would mean the size of
the problem and the credibility of the fix arrived as a single number that could
not be argued with separately.

## 2. Why this must come before the estimator

If censoring turns out to be rare, the estimator is irrelevant however good it
is. The kill criterion in `PREREGISTRATION.md` §6 fires on this milestone, not a
later one, and it fires on a number produced before any correction exists.

Running M2 first would mean discovering the problem was negligible only after
building the thing that solves it — and after acquiring a reason to prefer that
it was not negligible.

---

## 3. Tasks

| # | Task | Output |
|---|---|---|
| **M1-T1** | Aggregate the full trip archive in CI | 31 monthly marts, one manifest each |
| **M1-T2** | Resolve the `2026-04` anomaly | A stated cause, or a documented exclusion |
| **M1-T3** | Build the station-hour censoring join | Outage minutes per station-hour |
| **M1-T4** | Measure censoring exposure | The §6 criterion, with an interval |
| **M1-T5** | Characterise concentration | Share of censoring held by the worst stations |
| **M1-T6** | Establish the daily and weekly shape | The claim M0 could not make |
| **M1-T7** | Identify the never-stockout cohort | The held-out truth M2 depends on |
| **M1-T8** | Coverage report | Continuous, public, per `PREREGISTRATION.md` §3 |

### 3.1 M1-T1 — Aggregate the archive

29 GB across 31 monthly files plus 11 yearly archives. Runs on an Actions runner
adjacent to the bucket (M0-T3: 0.76 MB/s locally, eight hours for the monthly
files alone).

Each month produces `trip_counts_YYYYMM.parquet` and a manifest recording raw
rows, every category of dropped row, departures and arrivals counted, and the
UTC span. **A month without a manifest is not a mart** and may not be used.

Expected total ≈ 59 MB (M0-T5). If it materially exceeds that, storage is
re-planned before proceeding rather than after.

### 3.2 M1-T2 — The April anomaly

`2026-04` is 164.6 MB against 574.8 MB in March and 917.0 MB in May.

Checks, in order: uncompressed row count against neighbouring months; distinct
days present within the file; trips per day against the same month in 2025;
whether the shortfall is uniform across the month or confined to a range.

Three outcomes, each with a fixed consequence:

| Finding | Consequence |
|---|---|
| File is truncated | April excluded; every figure spanning it says so |
| April was genuinely disrupted | Retained, and treated as a known irregular period, never averaged silently |
| Cannot be determined | **Excluded**, and the inability to determine it is published |

### 3.3 M1-T3 — The censoring join

For each station and UTC hour, compute outage minutes by intersecting outage
intervals with the hour, separately by kind.

Rules, fixed here:

- **`empty` minutes censor departures. `full` minutes censor arrivals.** They are
  never summed into one "unavailability" figure; they suppress different events.
- **`offline` minutes censor nothing.** A station that is not there has no
  suppressed demand — it has no station. Offline hours are *excluded from the
  denominator*, not counted as zero-demand hours.
- An outage with an unobserved start or end contributes **no minutes**. It is
  counted, and the count is published beside every exposure figure.
- Hours only partly covered by collection are scaled by observed coverage within
  the hour, and hours below 50% coverage are excluded and counted.

### 3.4 M1-T4 — Exposure

The headline number of the milestone:

> What share of station-hours contain censoring, and what share of *observed
> departures* occur at stations that experience it?

Reported overall, and for the **top 200 stations by departures** — the population
the kill criterion names, and the one an operator would actually act on.

An interval accompanies every share. Days are the resampling unit, not
station-hours: station-hours within a day are heavily correlated and treating
them as independent would produce an interval far too narrow.

### 3.5 M1-T5 — Concentration

M0 saw the busiest 10% of affected stations account for 25% of empty outages, on
one evening. M1 establishes whether that holds over weeks.

Reported as a Lorenz curve and Gini over censored minutes per station, plus the
share held by the top 1%, 5% and 10%.

**Why it matters operationally:** concentrated censoring means a small
intervention could move the number. Spread censoring means it could not, and the
decision layer of M4 would be attacking a diffuse problem with a truck.

### 3.6 M1-T6 — The daily and weekly shape

M0's durations came from one Thursday evening. M1 reports them by hour-of-week,
which requires the §3 floor of `PREREGISTRATION.md` to be met first.

Specifically resolved here: **the four-to-one excess of `full` over `empty`
observed in M0.** If it holds across mornings and weekends it becomes a finding.
If it is an artefact of the evening peak, that is stated plainly and the M0
observation is retired.

### 3.7 M1-T7 — The never-stockout cohort

Stations with zero recorded `empty` minutes across the window, and with coverage
above the threshold — a station we barely watched is not a station that never
failed, and conflating the two would poison M2's held-out truth at the root.

Reported with their capacity and departure distributions against the rest of the
network, because §3.2 of the SRS requires the extrapolation gap to be visible
rather than assumed away. **If this cohort is too small or too unlike the rest,
M2's validation is compromised, and M1 must say so before M2 begins.**

---

## 4. What is explicitly out of scope

- Any estimate of hidden demand.
- Any statement that a station is under-served.
- Any ranking of stations by corrected demand.
- Any weather, calendar or covariate modelling.

M1 measures the hole. It does not fill it.

---

## 5. Data and coverage prerequisites

No exposure figure is published until `PREREGISTRATION.md` §3 is satisfied in
full: 21 continuous days, ≥ 95% coverage, ≥ 20,000 completed outages, and every
one of the 168 hour-of-week slots observed at least three times.

M1-T1, T2 and T7 depend on trip data only and proceed immediately. T3 through T6
wait.

---

## 6. Exit criterion

Fixed here, before the measurement, with three bands rather than pass/fail —
because the most likely outcome is the middle one and a binary criterion would
force it into the wrong box.

Let **E** = share of station-hours at the top 200 stations by departures that
contain `empty` censoring, over the analysis window.

| Band | | Consequence |
|---|---|---|
| **E < 2%** | Censoring is negligible | **Kill.** `PREREGISTRATION.md` §6 fires. Publish the negative result: the effect everyone assumes is there is not there. M2 onward abandoned |
| **2% ≤ E < 10%** | Censoring is real but modest | **Proceed, narrowed.** M2 runs on the affected subset only; no network-wide claim is made |
| **E ≥ 10%** | Censoring is substantial | **Proceed as specified** |

Two conditions apply to every band:

1. The interval is reported, and if it **straddles a band boundary**, the more
   conservative band governs. A point estimate of 10.4% with an interval reaching
   down to 8% is treated as the middle band.
2. The never-stockout cohort of M1-T7 must contain **at least 100 stations**. Below
   that, M2's validation cannot be run as specified regardless of E, and M1 must
   report the shortfall rather than proceeding and discovering it later.

---

## 7. Risks specific to M1

| Risk | Handling |
|---|---|
| Coverage never reaches §3 | Reported as the outcome. The project does not quietly proceed on thinner data |
| Zero-capacity stations leak into `empty` | The 53 known are tracked by id and checked explicitly, not assumed excluded |
| Outage minutes and trip hours misalign on time zone | The M0-T5 commute-peak check is re-run on the joined data, not just the trip data |
| The archive's stations do not cover the current network | M0-T4 found 327 live stations with no February trips, ~274 of them plausibly new. Exposure is computed only over stations present in both, and the excluded count is published |
| Concentration measured on too short a window | Reported by week as well as pooled, so instability is visible rather than averaged away |

---

## 8. Deliverables

1. 31 monthly marts with manifests.
2. A stated resolution of the April anomaly.
3. `Downfall_M1_Summary.md`, reporting E with an interval, the band that fired,
   the concentration curve, the hour-of-week shape, and the never-stockout cohort.
4. Coverage published continuously.
5. Tests for the join rules of §3.3 — in particular that `offline` minutes censor
   nothing and that flagged outages contribute no minutes.
6. `FINDINGS.md` updated as each result is established, not at the end.

---

## 9. Document control

| | |
|---|---|
| **Version** | 1.0 |
| **Date** | 2026-08-21 |
| **Status** | Approved, written before M1 ran |
| **Companions** | `Downfall_SRS_v1.0.md`, `PREREGISTRATION.md`, `Downfall_M0_Summary.md` |

Amendment rule per `PREREGISTRATION.md` §8. **The §6 exit criterion may not be
changed after the exposure figure is known.**
