"""
M1-T5 and M1-T6: where censoring sits, and when.

CONCENTRATION (T5)
------------------
M0 saw the busiest 10% of affected stations hold a quarter of empty outages, on
one evening. Measured here over the whole window, in censored SECONDS rather
than outage counts - a station that empties forty times for a minute is less of
a problem than one that empties once for four hours, and counts cannot tell
them apart.

The population is every station with docks, including the ones that never ran
out. Computing the Gini over affected stations only throws away exactly the
zeros that make censoring look concentrated, and answers a smaller question
than the one M4 needs ("could a few trucks move this?").

EMPTY and FULL are reported separately (M1 spec §3.3): they censor different
events and are never summed.

SHAPE (T6)
----------
Hour-of-week in New York local time, because riders keep local time and a UTC
slot splits the evening peak across two days twice a year.

Outage counts are divided by how many hours of each slot we actually watched.
Without that, a slot hit by a collection gap looks quiet, which is the
coverage artefact §3 exists to prevent.

The M0 asymmetry - full outnumbering empty four to one, 858 against 224 - was
one evening. This resolves it: if it holds in mornings and weekends it is a
finding, if it only holds in the evening the M0 observation is retired.

Usage:  python analysis/shape.py [--force]
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis.censoring import censored_minutes, coverage_by_hour, HOUR, MIN_COVERAGE  # noqa: E402
from analysis.duration import kaplan_meier, quantile                                  # noqa: E402
from analysis.exposure import floor_status                                            # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATIONS = ROOT / "data" / "stations.json"
NY = ZoneInfo("America/New_York")
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MIN_PER_CELL = 30       # as duration.py: below this a median is noise


def gini(values):
    """0 = spread evenly, 1 = all in one station. Zeros included on purpose."""
    v = sorted(values)
    n, total = len(v), sum(v)
    if n == 0 or total == 0:
        return float("nan")
    cum = sum((i + 1) * x for i, x in enumerate(v))
    return (2 * cum) / (n * total) - (n + 1) / n


def top_share(values, frac):
    v = sorted(values, reverse=True)
    k = max(1, round(len(v) * frac))
    return sum(v[:k]) / sum(v) if sum(v) else float("nan")


def slot(ts):
    t = datetime.fromtimestamp(ts, timezone.utc).astimezone(NY)
    return t.weekday() * 24 + t.hour


def concentration(rows):
    stations = json.loads(STATIONS.read_text(encoding="utf-8"))
    per = {k: defaultdict(float) for k in ("empty_s", "full_s")}
    for sid, s in stations.items():
        if s.get("cap"):            # 53 stations report capacity 0 permanently
            for k in per:
                per[k][sid] += 0.0
    for r in rows:
        for k in per:
            per[k][r["station"]] += r[k]

    print("\n=== M1-T5 concentration of censored time, per station ===")
    print("{:<8}{:>9}{:>10}{:>8}{:>9}{:>9}{:>9}{:>12}".format(
        "", "stations", "affected", "Gini", "top 1%", "top 5%", "top 10%",
        "Gini|aff"))
    for k, label in (("empty_s", "empty"), ("full_s", "full")):
        vals = list(per[k].values())
        aff = [x for x in vals if x > 0]
        print("{:<8}{:>9,}{:>10,}{:>8.3f}{:>8.1%}{:>9.1%}{:>9.1%}{:>12.3f}".format(
            label, len(vals), len(aff), gini(vals), top_share(vals, .01),
            top_share(vals, .05), top_share(vals, .10), gini(aff)))
        hours = sum(vals) / HOUR
        print("{:<8}total {:,.0f} station-hours censored; Lorenz (share of time "
              "held by the bottom X% of stations):".format("", hours))
        v = sorted(vals)
        print("{:<8}{}".format("", "  ".join(
            "{}%:{:.1%}".format(p, sum(v[:round(len(v) * p / 100)]) / sum(v))
            for p in (50, 75, 90, 95, 99))))
    # M0 measured top 10% of AFFECTED stations by outage count; same cut here,
    # by time, so the two can be compared directly.
    aff = [x for x in per["empty_s"].values() if x > 0]
    print("\n  M0 comparison: busiest 10% of affected stations hold {:.1%} of "
          "empty time (M0: ~25% of empty outages, one evening)".format(
              top_share(aff, .10)))


def shape(outages, runs):
    cov = coverage_by_hour(runs)
    watched = defaultdict(float)            # hours of each slot actually observed
    for h, s in cov.items():
        if s >= MIN_COVERAGE * HOUR:
            watched[slot(h)] += s / HOUR
    last = max(r["end"] for r in runs)

    starts = {k: defaultdict(int) for k in ("empty", "full")}
    events = {k: defaultdict(list) for k in ("empty", "full")}
    for o in outages:
        if o.kind not in starts or not o.start_seen:
            continue
        s = slot(o.start)
        if o.end is None:
            events[o.kind][s].append((max(last - o.start, 0), False))
        elif o.end_seen:
            events[o.kind][s].append((o.duration, True))
            starts[o.kind][s] += 1
        # end unseen -> no duration and not counted as a completed outage

    print("\n=== M1-T6 shape by hour-of-week, New York local time ===")
    print("completed outages STARTING per observed hour, network-wide, and "
          "Kaplan-Meier median duration (min)\n")
    blocks = [("night 00-06", range(0, 6)), ("am peak 06-10", range(6, 10)),
              ("midday 10-16", range(10, 16)), ("pm peak 16-20", range(16, 20)),
              ("evening 20-24", range(20, 24))]
    print("{:<11}{:<15}{:>8}{:>8}{:>8}{:>9}{:>9}".format(
        "", "", "empty/h", "full/h", "full:em", "med em", "med full"))
    for day_label, days in (("weekday", range(0, 5)), ("weekend", range(5, 7))):
        for blabel, hrs in blocks:
            ss = [d * 24 + h for d in days for h in hrs]
            w = sum(watched[s] for s in ss)
            e = sum(starts["empty"][s] for s in ss)
            f = sum(starts["full"][s] for s in ss)
            med = []
            for k in ("empty", "full"):
                ev = [x for s in ss for x in events[k][s]]
                q = quantile(kaplan_meier(ev), 0.5) if len(ev) >= MIN_PER_CELL else None
                med.append("{:.1f}".format(q / 60) if q is not None else "-")
            print("{:<11}{:<15}{:>8.1f}{:>8.1f}{:>8.2f}{:>9}{:>9}".format(
                day_label, blabel, e / w if w else 0, f / w if w else 0,
                f / e if e else float("nan"), *med))
        day_label = ""

    # The M0 question, slot by slot rather than by block.
    ratios = [starts["full"][s] / starts["empty"][s]
              for s in range(168) if starts["empty"][s]]
    above = sum(1 for r in ratios if r > 1)
    tot_e = sum(starts["empty"].values())
    tot_f = sum(starts["full"].values())
    print("\n  whole window: {:,} full vs {:,} empty completed outages, "
          "ratio {:.2f}".format(tot_f, tot_e, tot_f / tot_e))
    print("  full outnumbers empty in {} of {} hour-of-week slots; slot ratios "
          "range {:.2f} .. {:.2f}".format(above, len(ratios), min(ratios), max(ratios)))
    thin = [s for s in range(168) if watched[s] < 3]
    print("  slots watched under 3 hours: {}".format(len(thin)))


def main():
    met, _, outages, runs, _ = floor_status()
    if not met and "--force" not in sys.argv:
        print("PREREGISTRATION.md §3 floor not met. Nothing is reported.")
        return 2
    rows, excluded = censored_minutes(outages, runs)
    print("excluded, and published beside the figures:")
    for k, v in sorted(excluded.items()):
        print("  {:<24}{:>8,}".format(k, v))
    concentration(rows)
    shape(outages, runs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
