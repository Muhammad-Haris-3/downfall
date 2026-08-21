# Findings

Recorded as they are established. Numbers here are measured, never quoted.

---

## M0-T1 — The feed publishes every 70 seconds, and arrives already 2 minutes old

**Method.** 72 polls of `station_status.json` at a 10-second tick over 11.8
minutes, 2,508 stations per poll, zero failed requests. Raw capture retained.

### 1. The file regenerates every 70 seconds, exactly

Counting stations whose `last_reported` changed between consecutive polls:

```
0, 0, 1688, 0, 0, 0, 0, 0, 0, 2370, 0, 0, 0, 0, 0, 0, 1682, 0, ...
```

Nothing at all for six polls, then most of the city at once. The refresh events
fell at polls 2, 9, 16, 23, 30, 37, 44, 51, 58, 65 — **nine consecutive gaps of
exactly 70 seconds, with no variance.** `Last-Modified` on the response confirms
a regenerated file rather than per-station streaming.

**Polling faster than 70s returns a byte-identical file.** The measurement floor
is a property of the publisher, not of our effort — the same shape of result as
Headway's 20.0s, and it is settled before any collector is designed.

### 2. Readings are already ~2 minutes old when we receive them

Age of a value at the moment we read it, broken stations excluded:

| p10 | p50 | p90 | p99 |
|---|---|---|---|
| 71s | **122s** | 186s | 277s |

Two lags stack: the station's own report reaching Lyft, and the file's 70-second
regeneration cycle. **Every timestamp we hold is systematically late**, not
noisy-late.

This mostly cancels for *duration* questions — if an outage's start and end are
both shifted by the same ~2 minutes, its length survives. It does **not** cancel
for *point-in-time* questions. "Was this station empty at 08:00" is answerable
only to within about two minutes, and any morning-peak boundary drawn more
finely than that is false precision.

### 3. 87 stations (3.5%) carry no usable timestamp

87 of 2,508 report `last_reported = 86400` — 1970-01-02, a placeholder. They must
be excluded from any timing analysis rather than silently treated as very stale.
Whether they also carry unusable *counts* is not yet established.

### What this settles

| Question | Answer |
|---|---|
| Finest observable interval | **70 seconds** |
| Value of polling faster | **None.** Identical file |
| Systematic lag on every timestamp | **~122s, late** |
| Stations usable for timing | 2,421 of 2,508 |

### What it does not settle

Whether a 5-minute collection interval — the practical free-tier cadence — is
good enough. That depends on how long a stockout actually lasts, which is not
yet measured. It is the next task, and the answer is not assumed here.

---

## M0-T3 — What history exists, and where it must be processed

**Method.** Full listing of the public `tripdata` bucket, parsed rather than
eyeballed; schema read from a 2.8 MB Jersey City file rather than by downloading
a 1 GB NYC one.

### Inventory

| | |
|---|---|
| Monthly NYC files | **31**, `2024-01` through **`2026-07`**, 21.9 GB |
| Yearly NYC archives | 11, `2013`–`2023`, 7.1 GB |
| Jersey City files | 111, 0.16 GB — a separate, much smaller system |
| **Total** | **~29 GB** |

History is current to last month, and reaches back thirteen years.

### The download rate decides where the work runs

Measured against the bucket from this machine: **0.76 MB/s.**

| | At 0.76 MB/s |
|---|---|
| One month (~950 MB) | ~21 minutes |
| All monthly files | **~8 hours** |
| Everything | ~11 hours |

Pulling 29 GB onto a laptop to produce a few megabytes of counts is the wrong
shape. **Bulk download and aggregation belong in CI, where the runner sits next
to the bucket**, and only the aggregates come back. This is a measurement, not a
preference — and it was worth taking before designing the pipeline around a
local copy.

### One month is missing most of its data

`2026-04` is **164.6 MB**, against 574.8 MB in March and 917.0 MB in May. Ridership
does not fall by two thirds in April and then quadruple in May.

Either the file is truncated or April was genuinely disrupted. **Not yet
established which** — but any month-over-month figure spanning April is suspect
until it is, and no analysis may quietly average across it.

### Trip schema

13 columns: `ride_id`, `rideable_type`, `started_at`, `ended_at`,
`start_station_name`, `start_station_id`, `end_station_name`, `end_station_id`,
`start_lat`, `start_lng`, `end_lat`, `end_lng`, `member_casual`.

Timestamps carry milliseconds. One row per trip; departures and arrivals must be
derived from the two ends of the same row.

### Open, and blocking: can a trip be tied to a live station?

The whole project depends on joining historical demand to live outages. The two
sources do not obviously agree on identity:

| Source | Identifier |
|---|---|
| Live feed | `station_id` — **1,812 UUIDs and 696 numeric strings**, mixed |
| Live feed | `short_name` — `2377.01`, present on all 2,508 |
| Trip files | `start_station_id` — `HB102`, `JC009` in the Jersey City sample |

`short_name` is the likely bridge, with station `name` as a fallback. **Until the
match rate is measured on a real NYC month, the project has no established link
between demand and availability, and that is the next thing to settle.**

---

## M0-T4 — The join holds: 98.1% of trips reach a live station

The blocking question from M0-T3. Measured on February 2026 — **1,219,444 trips**,
2,214 distinct start stations — against the live station list.

`short_name` is the bridge. The live `station_id` is not: it is 1,812 UUIDs and
696 numeric strings, and appears nowhere in the trip files.

| | |
|---|---|
| Stations matched | 2,181 of 2,214 — **98.5%** |
| **Trips matched** | 1,194,777 of 1,218,325 — **98.07%** |
| Trips with no station id at all | 1,119 — 0.09% |

**The project is possible.** Historical demand can be tied to live availability
for essentially the whole network.

### What the missing 1.9% is

33 stations, 23,548 trips. They ran in February and are absent from the live feed
today — retired or renamed in the six months since. Eight of them still match a
live station **by name** while their `short_name` has changed, which is a rename,
not a closure.

Name is therefore a usable second pass, and it is deliberately not applied yet:
a name-only match is weaker evidence than an id match, and mixing the two without
recording which was used would make the join impossible to audit later.

### The other direction, which is the more interesting one

**327 live stations recorded zero trips in February.** Two different causes, and
they must not be pooled:

- **53 stations report `capacity = 0`.** Checked against the outages collected so
  far: they have produced **no** empty, full or offline rows, so they are not
  currently corrupting the record. Worth re-checking as coverage grows — a
  zero-capacity station reporting zero bikes forever would otherwise read as a
  permanent stockout and inflate every scarcity figure in the project.
- **The remaining ~274 have real capacity.** The likely explanation is that they
  opened between February and today; the live list is current, the trips are six
  months old. **Not established** — it needs a recent month to confirm, and until
  then no station is to be described as "new".

### Consequence for the design

The unit of analysis is `short_name`, not `station_id`. Station identity is
**not stable over time** — ids are reissued on rename — so every join must be
dated, and a station's history must be assembled by id *as of* the month in
question rather than by today's id.

---

## M0-T5 — A month of trips compresses 125x, and the clock is provably right

**Method.** February 2026 aggregated to per-station, per-hour counts.
237 MB zip in, **1.9 MB parquet out** — a 125x reduction with nothing needed for
the analysis discarded.

| | |
|---|---|
| Raw trips | 1,219,444 |
| Departures counted | 1,218,325 |
| Arrivals counted | 1,211,386 |
| Station-hours stored | 600,259 |
| **All 31 months, projected** | **~59 MB** |

**Thirteen years of demand fits inside a free 500 MB tier**, with room to spare.
That settles the storage question for the demand side.

### The commute peak validates the time zone conversion

Trip timestamps are naive **local** New York time; the live feed publishes a
**UTC** epoch. Mixing them silently misaligns every join by four or five hours,
and nothing about the output would look wrong.

Weekday departures by local hour, after conversion:

```
  05    10,317  #####
  06    25,370  ############
  07    48,035  #######################
  08    72,835  ####################################   <- morning peak
  ...
  16    69,880  ##################################
  17    92,749  ##############################################   <- evening peak
  18    79,822  #######################################
  03     1,682                                          <- trough
```

Peak at **08:00 and 17:00**, trough at **03:00**. That is the shape of commuting,
and it is only recoverable if the conversion is correct — an error of a few hours
would put the "morning peak" in the middle of the night. Weekends peak at
**14:00** instead, with no twin peaks at all, which is the shape of leisure.

**The clock is not asserted to be right. It reproduces a pattern whose answer was
known in advance** — the same test as a single-look A/B returning 5%.

### Two gaps, both counted rather than smoothed

- **1,119 trips (0.09%)** carry no start station. They are excluded from
  departures and reported, not dropped in silence.
- **6,939 more trips arrive nowhere** than depart nowhere — 0.57%. Every trip
  starts somewhere identifiable more reliably than it ends. Cause not yet
  established; it is small, and it is recorded because a 0.57% asymmetry that
  turns out to concentrate at particular stations would matter.

### Departures and arrivals are counted independently

A trip whose end is unusable still proves a bike **left**. Discarding the whole
row would understate demand exactly where the data is messiest, which tends to be
the busiest stations — the ones the project is about.

### 60% of station-hours are empty of trips and are not stored

Absent means zero. That is safe only for a station that existed and was open in
that hour, which is a separate question this pipeline deliberately does not
answer — see the open item in M0-T4 about stations that opened after February.

---

## M0-T6 — Half of stockouts clear within ten minutes, and that sets the cadence

**Method.** 3.0 hours of continuous collection, **Thursday 20 August, 15:50–18:50
New York time** — the evening peak. 155 published files, zero failed requests.
Durations estimated by Kaplan–Meier, so that outages still open when collection
stopped count as *at least this long* rather than being discarded.

Dropping them would have been the easy mistake: they are disproportionately the
long ones, and throwing them out roughly halves the answer.

| | empty | full |
|---|---|---|
| Usable outages | 224 | 858 |
| Ended within the window | 194 | 681 |
| Still open at the end | 30 | 177 |
| **Median duration** | **9.9 min** | **13.8 min** |
| 25th percentile | 4.7 min | 5.3 min |
| 75th percentile | 25.6 min | 47.8 min |
| Still unusable after 1 hour | 16.0% | 21.3% |

### The decision this settles

| | empty | full |
|---|---|---|
| Ends within one 70s publish cycle | **0.4%** | 0.6% |
| Ends within 5 minutes | 26.3% | 23.7% |

**Almost nothing is invisible.** Only ~0.5% of outages are shorter than a single
publish cycle, so the feed's own 70-second rhythm is fast enough to see
essentially every event. The measurement floor from M0-T1 is not a real
constraint here.

But a quarter of outages clear inside five minutes, so **a collector that samples
once every five minutes would blur about one in four.** The fix is the pattern
already used in Headway: don't sample on the cron, *run continuously between*
crons. A job that collects for 59 of every 60 minutes is blind for ~1.7% of the
day, against ~10% for a job that collects 4½ minutes out of every 5. Fewer, longer
jobs beat many short ones, because the loss lives at the boundaries.

### Two things this does NOT establish

**One evening is not a day.** 15:50–18:50 is the evening peak — when bikes pile
up in residential docks and drain from commercial ones. Morning is the same
process reversed, and 3am is neither. **Every figure above is an evening figure**
and none should be quoted as a daily rate.

**The long tail is cut off.** Nothing lasting more than three hours could be seen
to end. 16% of empty outages were still running at one hour and 10.9% at two, so
the tail is heavy and the true upper quantiles are worse than the table shows.
The median is solid; the 75th percentile is a floor.

### An early asymmetry, recorded but not yet believed

**Full docks outnumbered empty ones almost four to one** — 858 against 224 — and
lasted 40% longer. On this evidence the harder problem is not finding a bike, it
is finding somewhere to put one.

That is exactly what an evening peak should look like, which is why it is not yet
a finding. If it survives a morning and a weekend, it becomes one.

**Only 127 of 2,508 stations ran empty at all**, and the busiest 10% of those
accounted for a quarter of all empty outages. Scarcity is concentrated, not spread.

---

## M0-T7 — The collector rebuilt as an append-only log, and two bugs it exposed

The SQLite prototype stored one row per outage and edited it on recovery. That is
fine on a laptop and wrong in CI: an outage opens in one hourly job and closes in
a later one, so every run would rewrite history, and "append-only" would be a
promise made by careful code rather than a property of the store.

**Nothing is now ever rewritten.** Two events are appended - `open` and `close` -
and an outage is the pair. Public git history is the audit trail; a change to a
past line is a diff in a public commit.

### Bug 1: events filed under the wrong day

Events were filed by the timestamp they carried. But `last_reported` is *when the
station last checked in*, and a station that stopped reporting in May still
carries a May timestamp.

Result: one three-minute test wrote to **twelve files**, dated from 2026-05-28 to
2026-08-20. An hour of collection would have touched months of history on every
run - the precise thing the redesign was meant to make impossible.

Events are now filed by the day we **observed** them. The event's own timestamp
is kept in the record, where it belongs.

### Bug 2: outages already running when we first looked

On a cold start, 283 of 287 outages were already underway. Their apparent start
is the moment we first saw them, which is a lower bound wearing a measurement's
clothes - and the arithmetic gives a perfectly plausible duration either way.

Such opens are now flagged `o`, and any duration built from them is refused. The
same flag is applied after a gap longer than **10 minutes**, since an outage may
have begun at any point inside it. A normal one-minute handover is *not* flagged:
a minute sits inside the feed's own ~122s reporting lag, so the start is as well
known as any other.

### What the tests hold

15 tests, and most exist because the mistake was made rather than imagined:

- A switched-off station classifies as `offline`, never `empty`. It reports zero
  bikes, and 53 stations report zero capacity permanently — pooling them would
  manufacture shortage that never happened.
- An outage with an unseen start still computes a duration, **and is still
  refused**.
- Two opens with no close between them raise, rather than silently overwriting
  and producing a plausible outage of the wrong length.
- Writing to the log twice leaves the first bytes byte-identical.
- The poll interval is asserted to be `>= 60` (the feed's declared `ttl`) and
  `< 70` (its publish cycle). Both bounds have a reason, and the test states it.
- The thresholds in `PREREGISTRATION.md` §3 are asserted to still be there.

---

## M1-T2 — April is not missing data. It is the only month anybody compressed

The anomaly flagged in M0-T3: `2026-04` is 164.6 MB against 574.8 MB in March and
917.0 MB in May. The obvious reading was a truncated upload.

**Method.** A zip stores its index at the end of the file, so a range request for
the last 400 KB lists every member and its uncompressed size. 200 KB fetched
instead of 164 MB, and no month downloaded at all.

| Month | zip | **CSV inside** | ratio | ~trips |
|---|---|---|---|---|
| 2026-03 | 574.8 MB | 574.8 MB | 1.00 | 2.95M |
| **2026-04** | **164.6 MB** | **753.5 MB** | **0.22** | **3.87M** |
| 2026-05 | 917.0 MB | 917.0 MB | 1.00 | 4.70M |

**April holds more data than March, not less.** Its trip count sits exactly where
the seasonal ramp puts it. Checked across all 31 months: **every other month has a
ratio of 1.00** — the CSVs are *stored*, not deflated — and April alone is
actually compressed. It also uses a different member naming convention
(`-part1.csv` rather than `_1.csv`), so it was packaged by a different process.

**The anomaly was in the container, never the contents.** Inferring data volume
from file size was the error, and it would have excluded a complete month.

`2026-04` is **retained in full**. The M0-T3 flag is withdrawn.

### The full archive, measured rather than assumed

| | |
|---|---|
| Monthly files, 2024-01 → 2026-07 | **31** |
| Uncompressed | **22.5 GB** |
| **Trips** | **~115.2 million** |

Row counts are estimated from bytes at 194.9 B/row, calibrated against 2026-02
which was downloaded and counted in full. The estimate returns **1,219,290**
against a true **1,219,444** — an error of 0.01%, which is what makes the table
above worth quoting at all.

### A new flag, replacing the one just withdrawn

**February 2026 is 40% below February 2025** — 1.22M trips against 2.03M. January
is down 15% and March only 7%. February 2026 is specifically unusual, and it is
**the month M0-T4 and M0-T5 used for the join rate and the commute-peak check.**

Neither result plausibly depends on volume: a join rate is a ratio, and the
commute peak is a shape. But both were established on an atypical month, and that
is recorded here rather than discovered later. **M1 re-runs both on a normal
month before either is relied on.**

---

## M1-T0 — When M1 can actually report, measured from the publisher's own history

The trip archive covers whole months and appears after they end. How long after
was not known, and it decides when the censoring join can be computed at all —
that join needs trips and outages from the **same** period, and outage collection
only began on 2026-08-20.

**Method.** `LastModified` on each object in the bucket, against the last day of
the month it covers.

| Month | Published | Lag |
|---|---|---|
| 2026-03 | 2026-04-03 | 2 days |
| 2026-04 | 2026-05-04 | 3 days |
| 2026-05 | 2026-06-04 | 3 days |
| 2026-06 | 2026-07-06 | 5 days |
| 2026-07 | 2026-08-12 | 11 days |

**Median over the last twelve months: 3 days.** Far shorter than assumed, and the
one 11-day outlier is worth remembering when scheduling anything against it.

### Consequence

| Deliverable | Available |
|---|---|
| Exposure **E** — share of station-hours censored | **~11 Sept 2026**, on outage data alone |
| Departure-weighted exposure | **~4 Oct 2026**, once September's trips are published |
| First overlap of trips and outages | ~4 Sept 2026, covering 20–31 August only — 12 days, below the §3 floor |

**The kill criterion can still fire on schedule**, because the population it names
— the top 200 stations by departures — can be fixed from trip history that
already exists.

### The cohort rule, fixed now, before the outage window closes

> **The top-200 cohort is the 200 stations with the most departures across
> 2025-08 to 2026-07** — the twelve complete months preceding collection —
> identified by `short_name`, fixed once, and never redefined.

Defining it from data that **precedes** the measurement window is not a
convenience. Choosing the cohort from the same period whose censoring is being
measured would select stations partly on the outcome, and the exposure figure
would be biased upward by construction. Recorded here so the rule cannot be
adjusted once E is known.

---

## M1-T1 — 115 million trips aggregated, and the clock validated a second way

**Method.** One CI job per month, each downloading its own file next to the
bucket and deleting it after extracting counts. 30 months ran in parallel and the
whole archive finished in **about 90 seconds of wall clock**, against the eight
hours the same work would take over a home connection (M0-T3).

| | |
|---|---|
| Months | **31**, 2024-01 → 2026-07 |
| Raw trips | **115,022,000** |
| Departures counted | 114,916,337 |
| Arrivals counted | 114,649,938 |
| Station-hours | **30,602,910** |
| Output | **97 MB** |
| Rows dropped on the way in | 16,062 — **0.014%** |

The byte-based estimate from M1-T2 predicted 115.2M against an actual 115.0M —
**0.2% high** across the full archive, which is what makes reading a zip's index
instead of its contents a usable technique rather than a trick.

### Every DST drop is in November, and none is in March

Rows dropped for an unresolvable clock time, by month:

| Month | DST-ambiguous drops |
|---|---|
| 2025-01 | 0 |
| 2025-03 | **0** |
| 2025-06 | 0 |
| **2025-11** | **4,124 starts, 4,567 ends** |
| 2026-03 | **0** |

This asymmetry is the correct behaviour, and it is not obvious.

**Fall-back** repeats an hour: 01:30 on that Sunday happens twice, and a naive
local timestamp genuinely cannot say which. Those rows are unresolvable and are
dropped — ~4,000 of them, in November, in both directions.

**Spring-forward** skips an hour: 02:30 does not exist. A clock recording local
time never produces it, so **there is nothing to drop** — and zero is what
appears.

A time-zone bug would not respect that distinction. Getting exactly one
transition to produce drops, in the right direction, on a rule written before the
data was seen, is an independent check on the conversion that M0-T5's commute
peak could not provide.

---

## M1-T7a — The cohort, fixed before the window it will be measured over

`PREREGISTRATION.md` §6 evaluates the kill criterion on "the top 200 stations by
departures". **Which 200 has to be settled before the censoring figure exists**,
and not for tidiness:

> A station that stocked out heavily during the measurement window recorded fewer
> departures during that window. Rank on the same window and such stations are
> less likely to make the cohort — so the exposure figure, computed over the
> survivors, is biased downward by exactly the mechanism under study.

Defined instead over **2025-08 to 2026-07**, the twelve complete months preceding
collection, and written to `data/cohort_top200.json` with a SHA-256 over the
sorted station list. An analysis quoting a different digest is not quoting this
cohort.

| | |
|---|---|
| Stations with any departure, 12 months | 2,541 |
| Cohort | **200** — 7.9% of them |
| **Share of all departures** | **34.7%** |
| Entry cutoff | 57,781 departures |
| Busiest station | 165,362 departures |

**Demand is concentrated: 8% of stations carry 35% of it.** That is the first
network-wide structural fact this project has established, and it decides whether
the M4 decision layer is worth building — a fleet of three trucks can plausibly
matter to 200 stations, and could not matter to 2,541.

The generator refuses to overwrite an existing cohort file. Re-deriving it after
the exposure figure is known is precisely the failure the file exists to prevent.

---

## M1-T3a — The censoring join, and the four rules that make it honest

Built and tested before the outage record is deep enough to run it on, so the
rules were settled against cases worked out by hand rather than against results.

The join cuts outage intervals against station-hours. Four rules, each of which
would be invisible if broken, because a wrong answer here is still a plausible
one:

| Rule | What it prevents |
|---|---|
| **`empty` censors departures; `full` censors arrivals.** Never summed | A station with no docks records departures perfectly well. One "unavailability" figure would claim otherwise |
| **`offline` hours leave the denominator**, rather than entering as hours of zero demand | Dilution of every network rate, growing with the number of broken stations |
| **An outage with an unobserved boundary contributes no minutes** | A lower bound added into a total gives a total that is neither a bound nor a measurement |
| **Fractions are of the OBSERVED hour, never the nominal 3,600s** | An hour watched for 20 minutes and empty throughout was empty for all of what we saw. Reporting 33% would describe our collection schedule, not the station |

29 tests now, 14 of them on this join alone, every case checkable with a pen.

---

## M1-T8a — The hourly schedule did not fire, and the likely reason is the minute

The collection workflow was scheduled at `2 * * * *`. **The 00:02 run had still
not appeared 55 minutes later.** Manual dispatch works, and the workflow reports
as active, so this is the scheduler rather than the job.

GitHub's cron is best-effort and queues behind every other repository's
`0 * * * *`. The top of the hour is the most congested slot there is, and :02 is
inside it.

**Moved to `37 * * * *`.** A minute nobody else picks is the cheapest reliability
available, and it costs nothing.

This is not treated as fixed. It is a hypothesis with an obvious test — whether
the next run appears — and if the schedule remains unreliable the design has to
absorb it rather than assume it away, which is what `data/runs.ndjson` and the
gap flags exist for. **Coverage is measured, not promised**, and the §3 floor of
the pre-registration is enforced on measured coverage.

---

## M2-T0 — The estimator works in principle, and the first test of it was rigged

**This is preliminary and does not satisfy `PREREGISTRATION.md` §4.** That section
requires synthetic censoring drawn from the *observed* outage pattern of a matched
station, and the outage record is not yet deep enough. The patterns here are
generated. What this establishes is whether the method works at all — and now is
the safest moment to ask, because there is no exposure figure yet to want a
particular answer.

Six months, 199 stations of the fixed cohort, **760,783 station-hours**.

### Three methods

| | |
|---|---|
| **naive** | `λ = D`. Do nothing. What essentially every published analysis of this dataset does, and the thing the project claims is wrong |
| **scaled** | `λ = D / (1 − f)`. The obvious correction |
| **em** | Poisson `level[station] × shape[hour-of-week]`, fitted on what was observable, used to fill what was not, refitted |

### Results, over censored hours only

**Uniform censoring** — outage minutes placed at random, 15.0% of hours, mean f 0.35:

| method | median abs err | median signed | |
|---|---|---|---|
| naive | 33.3% | **−33.3%** | |
| scaled | 17.1% | +2.1% | pass |
| em | 18.4% | +4.1% | pass |

**Demand-driven censoring** — simulated minute by minute, 1.8% of hours, mean f 0.23:

| method | median abs err | median signed | |
|---|---|---|---|
| naive | 13.6% | **−13.6%** | |
| scaled | 6.4% | +5.3% | pass |
| em | **5.4%** | −4.1% | pass |

**The naive count is not noisy. It is wrong in one direction**, by 13% to 33%,
and the direction is the one that hides the problem: it understates demand
exactly where demand could not be recorded. That is the project's premise,
reproduced under conditions where the true answer was known.

Both corrections clear the pre-registered thresholds in both regimes. `em` wins
the realistic regime; `scaled` wins the artificial one, which is the ordering one
would want — the simple method is built for the easy case.

### The first version of this test was circular, and it flattered the answer

The original demand-driven simulator computed `f = lost / truth`. That makes
`observed = truth × (1 − f)` **true by construction** — and `scaled` inverts
exactly that identity. It scored **4.7%** on a test that had been handed the
answer.

Replaced with a mechanistic simulation: demand and returns are spread across the
minutes of the hour, stock is walked forward, and a departure meeting an empty
dock is lost. **Both `observed` and `f` are now outputs of that process** rather
than related by an identity the estimator can exploit.

`scaled` fell from 4.7% to 6.4%. The gap is small — and it was entirely the
simulator marking its own homework.

### A bug that only surfaced because numpy is strict

The marts store `dow_local` as `int8` to keep 30.6M rows small. Computing
hour-of-week as `dow * 24 + hour` overflows for Saturday: **6 × 24 = 144 wraps to
−112.**

`np.bincount` rejects negative indices, so it raised. **A slightly different
expression would not have.** It would have folded Saturday's hours silently into
Wednesday's and produced a perfectly plausible weekly profile, wrong in a way no
output inspection would reveal. The regression test names the day.

### Still unestablished

- Whether the real outage patterns behave like either simulated regime.
- Whether never-stockout stations resemble the stations the estimator will be
  applied to — SRS §3.2, and the reason §4 matches on capacity and departures.
- Anything about exposure. **M1 measures the hole; this only shows a tool that
  can fill a hole of known size.**
