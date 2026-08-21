# Downfall

**A station with no bikes records no demand. So the docks that fail most look
like the docks nobody wants — and the data quietly recommends starving them
further.**

Downfall watches every station in New York's bike share, records when each one
runs out and when it recovers, and estimates the demand that was never written
down.

> **Status: M0 complete, collecting.** No demand estimate is published yet, and
> no station is described as under-served. [`PREREGISTRATION.md`](PREREGISTRATION.md)
> fixes the coverage floor and the validation threshold that have to be cleared
> first, and both were written before the estimator existed.

---

## The problem, in one example

A station has ten bikes at eight in the morning. By half past, all ten are gone.
Between half past and nine, forty more people arrive, find an empty dock, and
walk away.

The trip file records **ten trips**.

Nothing anywhere records the forty. They did not take a bike, so no row exists.
Every public analysis of this data — and there are many — reads those ten trips
as the station's demand, and concludes it is quiet.

Then the obvious operational decision follows: put the bikes where the demand is.
The station gets fewer. It empties sooner. It records even less. **The measurement
causes the outcome it appears to describe.**

This is censoring, it is a solved problem in principle, and essentially nobody
applies it to this data.

## Why it can be checked rather than argued

The tempting version of this project asserts a hidden number and asks to be
believed. This one does not have to.

Some stations **never run out**. For those, observed demand *is* true demand, and
the answer is known. So the method can be marked: take a station that never
stocked out, hide its data during the hours a comparable station was empty,
re-estimate, and see whether the number it recovers is the number that was there
all along.

**The deliverable is not the demand estimate. It is the error of that estimate
against cases where the truth was already on the table** — and the threshold it
has to clear is written down in advance.

---

## What M0 established

Full record in [`FINDINGS.md`](FINDINGS.md). Each item is measured, and several
changed the design.

| | |
|---|---|
| **The feed republishes every 70 seconds, exactly** | Nine consecutive gaps, no variance. Polling faster returns a byte-identical file, so the observation floor belongs to the publisher, not to our effort |
| **Every reading arrives ~122s late** | Two lags stack. Durations survive this; *point-in-time* claims do not, and no boundary is drawn finer than two minutes |
| **Half of stockouts clear within 10 minutes** | Kaplan–Meier over 3 hours of the evening peak. A quarter clear inside five — which is why the collector runs continuously rather than sampling on the cron |
| **98.07% of trips join to a live station** | Measured on 1.2M February trips. `short_name` is the bridge; `station_id` is not |
| **A month of trips compresses 125×** | 237 MB in, 1.9 MB out. Thirteen years of demand fits a free tier |
| **87 stations report a 1970 timestamp** | Placeholders, excluded from timing rather than treated as very stale |
| **53 stations have zero capacity** | They report zero bikes forever. Pooled with real stockouts they would invent scarcity that does not exist |

### One check worth singling out

Trip times are naive **local**; the feed is **UTC**. Mixing them misaligns every
join by hours and leaves nothing that looks wrong.

After conversion, weekday departures peak at **08:00** and **17:00** and bottom
out at **03:00**; weekends peak once, at **14:00**. That is commuting, and then
leisure. The clock is not asserted to be correct — it reproduces a pattern whose
answer was known in advance.

---

## How the record stays honest

| Mechanism | What it prevents |
|---|---|
| **Append-only by construction.** Two events — `open` and `close` — are appended and never edited. An outage is the pair | A store where "append-only" is a promise made by careful code rather than a property of the file |
| **Public git history is the audit trail** | Silent retrospective editing. Any change to a past line is a diff in a public commit |
| **Coverage recorded per run** in `data/runs.ndjson` | A gap in collection reading as an hour when no station ever ran out |
| **Starts and ends that we did not see are flagged, not guessed** | The single most tempting error: stamping an unobserved boundary with a plausible time and inheriting a duration that was never measured |
| **Kaplan–Meier, not means** | Discarding outages still open when collection stopped. They are disproportionately the long ones, and dropping them roughly halves the answer |
| **Thresholds fixed before the estimator** | Choosing what counts as success after seeing which method won |

---

## Architecture

```
GBFS live feed  ·  Citi Bike trip archive  ·  Open-Meteo
   (all keyless, verified 2026-08-20)
        |
        v
GitHub Actions - a job of up to 350 min, checkpointing every 30
        |
        v
data/events/YYYY-MM-DD.ndjson     append-only open/close events
data/runs.ndjson                  coverage, per run
        |
        v
aggregation  ->  trip counts per station-hour (parquet)
        |
        v
censored-demand estimation  ->  validation against never-stockout stations
        |
        v
(M4+)  rebalancing plan, policy simulator, public scoreboard
```

Nothing runs on a laptop and nothing costs anything. The bulk trip archive is
29 GB and is downloaded by the CI runner, which sits next to the bucket — at the
0.76 MB/s measured from a home connection the same job would take eight hours.

---

## Milestones

| | Question | State |
|---|---|---|
| **M0** | Can outages be observed at all, and can trips be tied to stations? | ✅ Complete |
| **M1** | How much demand is censored, and where? | Collecting |
| **M2** | Can hidden demand be recovered on cases with a known answer? | — |
| **M3** | Does correcting for it change which stations rank as under-served? | — |
| **M4** | What should tonight's rebalancing do, and what is it worth? | — |
| **M5** | Published before the outcome, and scored after | — |
| **M6** | The application — seven surfaces, [SRS §6.5](Downfall_SRS_v1.0.md) | — |
| **M7** | Is service equitable, and what does equity cost in trips? | Declared |
| **M8** | Does any of it hold in a second city? | Declared |
| **M9** | Is a discharged e-bike an invisible stockout? | Declared |

## The honest limits

- **One city.** Everything here is New York and generalises to nobody until a
  second system is added.
- **A counterfactual cannot be scored the way a forecast can.** "This plan would
  have served 8% more trips" is a claim about a world nobody ran. Simulator
  fidelity will be reported against the *observed* policy first, and the
  distinction will not be blurred.
- **Coverage will not reach 100%.** GitHub's scheduler is best-effort and skips
  runs under load. That is not worked around because it cannot be — it is
  recorded, and gaps disqualify the outages that span them.
- **Demand is not desire.** What can be estimated is how many people would have
  taken a bike from a dock that had one. People who checked an app, saw an empty
  station and never left the house are not in this data and never will be.

## Run it

```bash
python collector/collect.py 5      # collect for five minutes
```

No key, no account, no database. Python 3.13 and the standard library; pandas and
pyarrow for the trip aggregation only.
