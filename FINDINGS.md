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
