# CLAUDE.md

Guidance for working in this repository.

## What this project is

**A station with no bikes records no demand.** Downfall records when every station
in New York's bike share becomes unusable, estimates the demand those periods
suppressed, and tests whether correcting for it changes which stations an
operator would call under-served.

The subject is **data that does not exist**. Nobody counted the riders who found
an empty dock. That is why almost every published analysis of this dataset reads
departures as demand, and why the central claim here has to be checkable rather
than asserted — see `PREREGISTRATION.md` §4.

**Status:** M0 complete, collection running hourly on GitHub Actions. No demand
estimate exists and no station has been ranked.

## Commands

```bash
python collector/collect.py 5              # collect for five minutes
python collector/collect.py                # collect until stopped
python collector/summarise_run.py          # the commit message CI writes
python analysis/duration.py                # Kaplan-Meier over the event log
python pipeline/aggregate_trips.py data/202602.zip
python -m pytest tests/ -v
gh workflow run collect.yml -f minutes=3   # trigger a short collection in CI
```

## Architecture

```
GBFS station_status  ->  hourly Actions job, 59 min of every 60
                     ->  data/events/YYYY-MM-DD.ndjson   append-only open/close
                     ->  data/runs.ndjson                coverage, per run
                     ->  committed back to this repo by the job itself

Citi Bike archive    ->  aggregation (CI, next to the bucket)
                     ->  data/marts/trip_counts_YYYYMM.parquet
                     ->  data/marts/manifest_YYYYMM.json
```

`analysis/events.py` is the **only** place `open`/`close` events are paired into
outages. Every analysis inherits its rules about what is usable. Do not re-derive
that pairing elsewhere.

## Invariants — do not change these to make code or numbers nicer

Most of these exist because the mistake was actually made. `PREREGISTRATION.md`
states in its own §1 what had already been seen when it was written.

- **`offline` takes precedence over `empty` in `classify()`.** A switched-off
  station reports zero bikes, and 53 stations report `capacity = 0` permanently.
  Classifying either as a stockout manufactures shortage that never happened.
- **Events are filed by the day they were OBSERVED**, never by the timestamp they
  carry. `last_reported` is when a station last checked in — one offline since
  May still carries May. Filing by it scattered a three-minute test across twelve
  files spanning three months.
- **An outage with an unobserved start or end has no duration.** It still
  *computes* one, which is exactly why it must be refused. `Outage.duration`
  gives the arithmetic; **`Outage.usable_duration` is the one analyses may use.**
- **Kaplan–Meier, never means.** Outages still open when the log ends are
  disproportionately the long ones; dropping them roughly halves the answer.
- **`POLL_S` stays in `[60, 70)`.** 60 is the feed's declared `ttl` — polling
  faster ignores what the publisher asked and buys nothing, since timestamps come
  from the feed's clock. 70 is the publish cycle; slower would skip files. Both
  bounds are asserted by a test that states the reason.
- **Nothing is ever rewritten in `data/events/`.** An outage is an `open` and the
  `close` that follows. If a store update ever looks necessary, the design is
  wrong — that is why the SQLite prototype was thrown away.
- **A gap in collection must be visible as a gap.** Every run appends its own
  coverage to `data/runs.ndjson`. GitHub's cron is best-effort and skips runs
  under load; that is not worked around because it cannot be. Expect ~95%, not
  100%.
- **No rate, estimate or ranking is published before `PREREGISTRATION.md` §3** —
  21 continuous days, ≥95% coverage, ≥20,000 completed outages, all 168
  hour-of-week slots seen three times. A provisional figure captioned "early" is
  how a stopping rule gets abandoned without anyone deciding to.
- **The M1 exit bands may not move after E is known** (`Downfall_M1_Spec.md` §6),
  and an interval straddling a boundary takes the more conservative band.
- **A counterfactual is not a measurement.** Simulator fidelity against the
  *observed* policy is published beside every "would have served N more trips"
  figure. FR-23.

## Conventions

- **The collector uses the standard library only.** It runs every hour forever; a
  dependency it does not have cannot break it at 3am. pandas and pyarrow are for
  trip aggregation, which runs in a different job.
- **Docstrings explain *why*, and record what broke.** Several carry the bug that
  motivated the code — the twelve-file scatter, the cold-start censoring, the
  lambda that turned a 20-second groupby into a 20-minute one. Preserve that when
  editing; do not compress them into descriptions of what the code does.
- **Tests exist for the guarantees, not the plumbing**, and each says why. The
  append-only test writes twice and compares the first bytes; the lost-close test
  expects a raise rather than a plausible wrong answer.
- **`.gitignore` is a deny-all with named exceptions.** A 237 MB source zip was
  committed once and the history had to be rewritten. Do not convert it back to
  an ignore-list. `data/events/`, `data/state/open.json`, `data/runs.ndjson`,
  `data/stations.json` and mart *manifests* are tracked; marts, archives and
  databases are not.
- **State writes are atomic** (`tmp` then `replace`). A killed job must not leave
  half a state file, and the job is killed on a schedule.
- **Timestamps come from the feed, never from local wall clock.** Our clock is
  ~122s behind the reading anyway; the feed's is internally consistent.
- **Trip times are naive local; the feed is UTC.** Convert once, at ingest.
  Impossible DST clock times are dropped and counted, never shifted — a shifted
  timestamp is a fabricated one. The conversion is validated by recovering the
  08:00/17:00 commute peak, not by inspection.

## Reference documents

`Downfall_SRS_v1.0.md` (requirements, BQ-* questions, FR-*/NFR-*),
`Downfall_M0_Summary.md` (every measurement, what broke, what was decided —
read §1.1 first, it states a real gap in the record),
`Downfall_M1_Spec.md` (the current milestone and its exit bands),
`PREREGISTRATION.md` (read §1 first — it states what had already been seen),
`FINDINGS.md` (results as established, in order).
