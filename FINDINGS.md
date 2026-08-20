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
