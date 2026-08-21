"""
How many minutes of each hour was each station unable to serve?

This is the join the whole project turns on: outage intervals, cut against
station-hours, so that a demand figure can be set beside the time during which
demand could not be recorded.

The rules are fixed in `Downfall_M1_Spec.md` §3.3 and are not negotiable here:

  EMPTY censors DEPARTURES. FULL censors ARRIVALS. They are never summed into
  one "unavailability" number, because they suppress different events. A station
  with no docks records departures perfectly well.

  OFFLINE CENSORS NOTHING. A station that is not installed has no suppressed
  demand - it has no station. Its hours leave the denominator entirely rather
  than entering it as hours of zero demand, which would dilute every rate.

  AN OUTAGE WITH AN UNOBSERVED BOUNDARY CONTRIBUTES NO MINUTES. Its length is a
  lower bound, and a lower bound added into a total produces a total that is
  neither a bound nor a measurement.

  AN HOUR WE BARELY WATCHED IS NOT AN HOUR NOTHING HAPPENED IN. Minutes are
  expressed against observed coverage, and an hour below the coverage floor is
  dropped and counted rather than scaled up from almost nothing.
"""

import json
from collections import defaultdict
from pathlib import Path

from analysis.events import coverage, load_outages

ROOT = Path(__file__).resolve().parent.parent
STATIONS = ROOT / "data" / "stations.json"

HOUR = 3600
MIN_COVERAGE = 0.5      # M1 spec §3.3: below this the hour is dropped, not scaled


def hour_floor(ts):
    return ts - (ts % HOUR)


def split_by_hour(start, end):
    """Yield (hour_start, seconds_in_that_hour) for an interval."""
    if end <= start:
        return
    h = hour_floor(start)
    while h < end:
        lo = max(start, h)
        hi = min(end, h + HOUR)
        if hi > lo:
            yield h, hi - lo
        h += HOUR


def coverage_by_hour(runs=None):
    """Observed seconds per UTC hour, from the per-run record."""
    if runs is None:
        _, _, runs = coverage()
    out = defaultdict(float)
    for r in runs:
        for h, secs in split_by_hour(r["start"], r["end"]):
            out[h] += secs
    # Overlapping runs would double-count. They are prevented by the workflow's
    # concurrency group, but a cap costs nothing and turns a silent inflation
    # into a harmless clamp.
    return {h: min(s, HOUR) for h, s in out.items()}


def station_short_names():
    if not STATIONS.exists():
        return {}
    raw = json.loads(STATIONS.read_text(encoding="utf-8"))
    return {sid: v.get("short") for sid, v in raw.items()}


def censored_minutes(outages=None, runs=None, min_coverage=MIN_COVERAGE):
    """Returns (rows, excluded) where rows are dicts, one per station-hour seen.

    `excluded` counts what was refused and why, so the caller can publish it
    beside the rate rather than discovering the gap later.
    """
    if outages is None:
        outages = load_outages()
    cov = coverage_by_hour(runs)
    shorts = station_short_names()

    acc = defaultdict(lambda: {"empty_s": 0.0, "full_s": 0.0, "offline_s": 0.0})
    excluded = {"unobserved_boundary": 0, "still_open": 0, "offline_outages": 0}

    for o in outages:
        if o.end is None:
            excluded["still_open"] += 1
            continue
        if not (o.start_seen and o.end_seen):
            # A lower bound is not a measurement. Counted, never added.
            excluded["unobserved_boundary"] += 1
            continue
        if o.kind == "offline":
            excluded["offline_outages"] += 1
        field = {"empty": "empty_s", "full": "full_s", "offline": "offline_s"}[o.kind]
        for h, secs in split_by_hour(o.start, o.end):
            acc[(o.station, h)][field] += secs

    rows = []
    dropped_low_coverage = 0
    for (station, h), v in acc.items():
        covered = cov.get(h, 0.0)
        if covered < min_coverage * HOUR:
            dropped_low_coverage += 1
            continue
        # An hour that is entirely offline is not an hour of zero demand. It
        # leaves the denominator rather than entering it as a usable hour.
        if v["offline_s"] >= covered:
            continue
        rows.append({
            "station": station,
            "short": shorts.get(station),
            "hour_utc": h,
            "covered_s": covered,
            "empty_s": min(v["empty_s"], covered),
            "full_s": min(v["full_s"], covered),
            "offline_s": min(v["offline_s"], covered),
            # Share of the OBSERVED hour, never of the nominal 3600s. An hour we
            # watched for twenty minutes and saw empty throughout was empty for
            # all of what we saw, and reporting 33% would be a coverage artefact.
            "empty_frac": min(v["empty_s"], covered) / covered,
            "full_frac": min(v["full_s"], covered) / covered,
        })
    excluded["low_coverage_hours"] = dropped_low_coverage
    return rows, excluded
