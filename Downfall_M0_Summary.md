# Downfall — M0 Summary: can the missing demand be seen at all?

**Milestone:** M0 — Observability, join, and the walking skeleton
**Author:** Muhammad Haris Khokhar
**Date:** 2026-08-21
**Status:** **Complete.** Collection running unattended on GitHub Actions.
**Depends on:** `Downfall_SRS_v1.0.md`, `PREREGISTRATION.md`

---

## 1. Exit criterion

M0 asked two questions, either of which could have ended the project on day one:

> **Can a station's outages be observed finely enough to matter — and can the
> historical trip record be tied to the stations that had them?**

**Answer: yes to both, with two limits that constrain what may be claimed.**

| | Measured | Verdict |
|---|---|---|
| Publish cycle | **70s**, exactly, no variance | Fine enough — median outage is ~10 min |
| Outages shorter than one cycle | **0.4%** | Essentially nothing is invisible |
| Reading staleness at read time | **~122s**, systematically late | Durations survive; point-in-time claims limited to ±2 min |
| Trip → station join | **98.07%** of 1.2M trips | Proceed |
| History that fits a free tier | 237 MB → **1.9 MB** per month | Proceed |

**Proceed to M1.**

### 1.1 A gap in the record, stated rather than glossed

**There is no `Downfall_M0_Spec.md`, because none existed while M0 ran.** M0 was
exploratory: the questions were known, the thresholds were not, and inventing a
specification afterwards and dating it earlier would be exactly the failure this
project is about.

`PREREGISTRATION.md` was written at the *end* of M0 and says so in its own §1,
listing everything already seen before it was written. From M1 onward each
milestone gets a spec before it runs. For M0 itself, the claim that no threshold
was moved to fit a result rests on nothing but the author's word — recorded here
because a reader is entitled to know which claims are backed by mechanism and
which are not.

---

## 2. What was done

| Task | Status |
|---|---|
| **M0-T1 Feed refresh rate** | **Done.** 70s, from 72 polls at a 10s tick |
| **M0-T2 Collector, first cut** | **Superseded** — SQLite prototype, replaced in M0-T7. See §4.1 |
| **M0-T3 Source inventory** | **Done.** 29 GB, 2013 → 2026-07; download rate measured |
| **M0-T4 The join** | **Done.** 98.07% on `short_name`. The task the milestone exists for |
| **M0-T5 Demand aggregation** | **Done.** 125× compression; clock validated against the commute peak |
| **M0-T6 Outage duration** | **Done.** Kaplan–Meier over 3.0 h of the evening peak |
| **M0-T7 Collector rebuild and ship** | **Done.** Append-only event log, hourly on Actions, 15 tests |

---

## 3. Verification performed

### 3.1 The publish cycle is the publisher's, not ours

72 polls at 10s, 2,508 stations each, zero failures. Counting stations whose
`last_reported` changed between consecutive polls:

```
0, 0, 1688, 0, 0, 0, 0, 0, 0, 2370, 0, 0, 0, 0, 0, 0, 1682, 0, ...
```

Nothing for six polls, then most of the city at once. Refresh events at polls 2,
9, 16, 23, 30, 37, 44, 51, 58, 65 — **nine consecutive gaps of exactly 70
seconds**. `Last-Modified` confirms a regenerated file rather than per-station
streaming.

Polling faster returns a byte-identical file. **This is a floor we cannot buy our
way under**, and knowing it before designing the collector is what stopped an
argument about cadence from being settled by preference.

### 3.2 The clock, validated against a known answer

Trip timestamps are naive **local**; the feed publishes **UTC**. Mixing them
misaligns every join by four or five hours and leaves nothing that looks wrong.

After conversion, weekday departures by local hour:

| Hour | Departures | |
|---|---|---|
| 03 | 1,682 | trough |
| 08 | **72,835** | morning peak |
| 17 | **92,749** | evening peak |

Weekends peak once, at 14:00, with no twin peaks. **That is commuting, and then
leisure.** The conversion is not asserted to be correct; it reproduces a pattern
whose answer was known in advance. An error of a few hours would have put the
morning peak in the middle of the night.

### 3.3 The join, measured rather than assumed

`station_id` in the live feed is 1,812 UUIDs and 696 numeric strings, and appears
nowhere in the trip archive. `short_name` is the bridge.

| | |
|---|---|
| Stations matched | 2,181 of 2,214 — 98.5% |
| **Trips matched** | 1,194,777 of 1,218,325 — **98.07%** |

The unmatched 1.9% is 33 stations that ran in February and are absent today.
Eight of them still match a live station **by name** with a changed `short_name`
— a rename, not a closure. Name matching is therefore available as a second pass
and was **deliberately not applied**: a name match is weaker evidence, and mixing
the two without recording which was used makes the join unauditable.

### 3.4 Duration, with censoring handled rather than avoided

3.0 hours, Thursday 20 August, 15:50–18:50 New York — the evening peak. 155
published files, zero failed requests.

| | empty | full |
|---|---|---|
| Usable outages | 224 | 858 |
| Still open at the end | 30 | 177 |
| **Median duration** | **9.9 min** | **13.8 min** |
| Still unusable after 1 h | 16.0% | 21.3% |

Kaplan–Meier, not means. Outages still open when collection stopped are
disproportionately the long ones; discarding them roughly halves the answer.

### 3.5 The append-only guarantee, tested by attempting to break it

15 tests. The ones that matter:

- Writing to the log twice leaves the first bytes **byte-identical**.
- Two `open` events with no `close` between them **raise**, rather than silently
  overwriting and producing a plausible outage of the wrong length.
- An outage with an unobserved start still computes a duration, **and is still
  refused**.
- A switched-off station classifies as `offline`, never `empty`.
- `POLL_S` is asserted `>= 60` (the declared `ttl`) and `< 70` (the publish
  cycle). Both bounds have a reason and the test states it.
- The thresholds in `PREREGISTRATION.md` §3 are asserted to still be present.

---

## 4. Problems found

### 4.1 The first collector would have rewritten history every hour

The prototype stored one row per outage and updated it on recovery. On a laptop
that is fine. In CI an outage opens in one hourly job and closes in a later one —
so every run would have edited past records, and "append-only" would have been a
promise made by careful code rather than a property of the store.

**Rebuilt as an event log.** Two events appended, never edited; an outage is the
pair. Public git history is the audit trail.

### 4.2 Events were filed under the wrong day, by three months

Events were filed by the timestamp they carried. But `last_reported` is *when a
station last checked in*, and a station that stopped reporting in May still
carries a May timestamp.

A single three-minute test wrote to **twelve files, dated 2026-05-28 through
2026-08-20**. An hour of real collection would have touched months of history on
every run — precisely what the rebuild in §4.1 existed to prevent.

**Filed by observation date now.** The event's own timestamp stays in the record.

### 4.3 On a cold start, 283 of 287 outages were already running

Their apparent start is the moment we first looked, which is a lower bound
wearing a measurement's clothes — and the arithmetic yields a perfectly plausible
duration either way. This is the single most tempting error in the project, and
it is invisible in the output.

**Flagged and refused.** The same flag applies after any gap longer than ten
minutes. A normal one-minute handover is *not* flagged: a minute sits inside the
feed's own ~122s reporting lag, so the start is as well known as any other.

The mechanism fired on the first production run, unprompted — that commit reads
*"7 outages ended during the handover and carry no duration."*

### 4.4 A 237 MB source file was committed to git

Caught while the repository was still local. History rewritten; the repository
went from 61 MB to 106 KB with all commits intact. `.gitignore` is now a deny-all
with named exceptions, which is the version of that file that could not have let
it happen.

### 4.5 Two station populations that would manufacture scarcity

- **87 stations** report `last_reported = 86400` — a 1970 placeholder. Excluded
  from timing by threshold.
- **53 stations** report `capacity = 0`. They report zero bikes permanently, and
  pooled with real stockouts they would read as a permanent shortage. Currently
  producing no outage rows; flagged for re-checking as coverage grows.

### 4.6 One month of the archive is missing most of its data

`2026-04` is 164.6 MB against 574.8 MB in March and 917.0 MB in May. Ridership
does not fall by two thirds and then sextuple.

**Not established** whether the file is truncated or April was genuinely
disrupted. No analysis may average across it until it is.

---

## 5. Decisions taken

### 5.1 Collect continuously, do not sample

A quarter of outages clear within five minutes, so a collector *sampling* every
five minutes blurs one in four. What matters is not how often the job starts but
how much of the clock it watches.

| | Handovers/day | Blind |
|---|---|---|
| 4½ min of every 5 | 288 | ~10% |
| **59 min of every 60** | **24** | **~1.7%** |

### 5.2 Poll at 60s, not 35s

The feed declares `ttl: 60`. Polling faster ignored what the publisher asked for
and bought nothing: timestamps come from the feed's clock, not ours, so noticing
a file late shifts nothing. 60s remains strictly faster than the 70s publish
cycle, so no file is skipped — and a skip, should publication ever accelerate, is
now detected and counted.

### 5.3 Files in git, not a hosted database

Collection could begin the same day, with no account and no credential, and the
public history is itself the audit trail. Availability data cannot be
back-filled, so starting the clock outweighed the convenience of SQL. Postgres
arrives when the application needs to query, not before.

### 5.4 Bulk aggregation runs in CI

Download rate from a home connection measured at **0.76 MB/s** — eight hours for
the monthly archive. The runner sits next to the bucket. This is a measurement,
not a preference, and it was worth taking before designing a pipeline around a
local copy.

---

## 6. What this means for the project

**The premise survived contact with the data.** At a single observed moment, 473
of 2,508 stations were unusable — 176 empty, 297 full. There is a large amount of
censoring to measure, which is the thing M0 most needed to be true.

**The observation floor is not a constraint.** 0.4% of outages are shorter than
one publish cycle. Whatever limits this project, it will not be the feed's
resolution.

**The join holds**, so demand and availability can be tied together at all. That
was the one result capable of ending the project outright.

**One early asymmetry, recorded and not yet believed.** Full docks outnumbered
empty ones roughly four to one and lasted 40% longer. If that survives a morning
and a weekend, the harder problem is not finding a bike but finding somewhere to
put one — which would be a finding. On one evening it is only what an evening
peak should look like.

### 6.1 What M0 does not establish

- **One evening is not a day.** Every duration figure above is an evening figure.
- **The long tail is cut off.** Nothing over three hours could be seen to end;
  16% of empty outages were still running at one hour. Upper quantiles are floors.
- **Nothing about the estimator.** No demand has been recovered, no station has
  been ranked, and the validation of `PREREGISTRATION.md` §4 has not been
  attempted. M0 establishes that the question can be asked, not that it can be
  answered.

---

## 7. Next

M1 asks: **how much demand is censored, and where?**

It cannot report a rate until the coverage floor of `PREREGISTRATION.md` §3 is
met — 21 continuous days at ≥ 95% coverage, ≥ 20,000 completed outages, and every
hour of the week observed at least three times. At the observed rate the outage
count arrives in about three days; **the 21 days is the binding constraint, and
it exists precisely because M0 saw one Thursday evening.**

Work that does not depend on that floor proceeds in parallel: aggregating the
full archive in CI, resolving the April anomaly, and building the estimator
against never-stockout stations — which needs only trip data, already in hand.

---

## 8. Document control

| | |
|---|---|
| **Version** | 1.0 |
| **Date** | 2026-08-21 |
| **Status** | M0 complete; collection unattended |
| **Companions** | `Downfall_SRS_v1.0.md`, `PREREGISTRATION.md`, `FINDINGS.md` |
| **Known gap** | No M0 spec existed; see §1.1 |
