# Pre-registration

**v1.0 — written 2026-08-21, after M0 and before any demand estimator exists.**

The point of this document is that the thresholds below cannot be chosen after
the results are known. It is committed to a public repository, and the constants
it fixes live in code where the test suite asserts them against this text.

---

## §1 What had already been seen when this was written

Stating it first, because a pre-registration written after looking at *some* data
is only honest about the part it declares.

M0 was complete. That means the following were already known and are **not**
predictions:

- The feed republishes every 70s; readings arrive ~122s late; 87 stations carry a
  placeholder timestamp; 53 report zero capacity.
- Over 3.0 hours of one Thursday evening peak: median empty duration 9.9 min,
  median full duration 13.8 min, 224 usable empty outages and 858 full.
- 98.07% of February 2026 trips join a live station on `short_name`.
- A month of trips aggregates to 1.9 MB; all history to ~59 MB.
- Full docks outnumbered empty ones roughly four to one **on that evening**.

No demand estimator had been written, no station had been ranked, and no
censoring correction had been attempted. Everything in §3 onward concerns work
not yet begun.

---

## §2 The claim this project intends to test

> Observed departures understate true demand at stations that run out, and
> correcting for that changes which stations are identified as under-served.

Two parts, and they fail independently. The correction may be recoverable and yet
change no ranking; the ranking may change and the correction be unverifiable.
**Both are reported either way.**

---

## §3 Coverage floor, before any rate is published

No stockout rate, demand estimate, or station ranking is published until **all**
of the following hold:

| | Threshold |
|---|---|
| Continuous collection | **≥ 21 days** |
| Coverage within that window | **≥ 95%** of wall-clock, from `data/runs.ndjson` |
| Completed outages, start and end both observed | **≥ 20,000** |
| Distinct days covering every hour of the week | **≥ 3** observations of each of the 168 hour-of-week slots |

The last row exists because M0 saw one evening. An evening is not a day, and a
figure built from evenings would describe the evening while claiming to describe
the network.

**Outages flagged `o` (start not seen) or `u` (end not seen) are excluded from
every duration figure.** They are counted, and the count is published alongside.

---

## §4 The validation that decides whether the method is usable

Stations that never run out have observed demand equal to true demand. That is
the held-out truth.

**Procedure**, fixed here in full:

1. Select stations with zero recorded stockout minutes over the analysis window.
2. For each, impose synthetic censoring drawn from the *observed* outage pattern
   of a matched station that does run out — matched on capacity and on total
   departures, not on anything the estimator uses.
3. Estimate demand from the censored series.
4. Compare with the true, uncensored figure.

**Pass requires both:**

- Median absolute percentage error **≤ 20%**
- Median *signed* percentage error within **±10%** — the estimator must not be
  systematically high or low. A method that is wrong by 20% in a consistent
  direction is worse than useless here, because the entire claim is about a
  systematic direction.

**If validation fails, the central claim is withdrawn, not caveated.** The
project then reports what M1 measured about censoring exposure, and states that
recovering the hidden demand was attempted and did not work.

---

## §5 The ranking test

Stations are ranked twice: by observed departures, and by estimated true demand.

The claim in §2 is supported only if **rank change is positively associated with
censored exposure** — stations that spent more time empty move up — at
**p < 0.01**, one-sided, with the effect size reported in rank positions per hour
of censoring.

A statistically significant but tiny effect is a null result and will be
described as one. **The effect size is the finding; the p-value is a gate.**

---

## §6 What would kill the project

Any one of these ends it, and the negative result is published with the same
prominence a positive one would get:

- **Censoring is too rare to matter.** If fewer than 2% of station-hours at the
  top-200 stations by departures are censored, there is nothing meaningful to
  recover regardless of method.
- **Validation fails** under §4.
- **The ranking does not move** under §5.
- **Coverage never reaches §3** — for example because the feed changes or access
  is withdrawn.

---

## §7 Declared in advance about the operational layer (M4+)

The rebalancing plan and simulator are **not** validated by §4, and no claim of
the form "this plan would have served N more trips" is a measurement. It is the
output of a model of a world nobody ran.

Before any such number is published, the simulator must first be scored on its
ability to reproduce the **observed** policy's outcomes on held-out days, and
that fidelity figure must be published next to every counterfactual it is used
to produce.

---

## §8 Amendments

Any change to this document is a new numbered version, committed separately, with
the reason stated and the previous version left intact in git history. An
amendment made after seeing a result says so in its first line.

No amendment may weaken §4 or §5 after the corresponding analysis has been run.
