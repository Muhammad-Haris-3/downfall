"""
M1-T4 — how much of the network's demand is censored?

The headline number of the milestone, and the one the kill criterion fires on.

THIS SCRIPT REFUSES TO REPORT E UNTIL THE FLOOR IS MET
------------------------------------------------------
`PREREGISTRATION.md` §3 sets a coverage floor: 21 continuous days, >=95%
coverage, >=20,000 completed outages, and every one of the 168 hour-of-week
slots seen at least three times. Until all four hold, this prints progress
toward them and nothing else.

That is enforced here rather than remembered, because the failure mode is not
dishonesty - it is a provisional figure captioned "early" that gets quoted
without the caption, and then becomes the number everyone knows. A stopping rule
gets abandoned that way without anyone ever deciding to abandon it.

THE EXIT BANDS, from `Downfall_M1_Spec.md` §6, fixed before any measurement:

    E < 2%      kill. The effect everyone assumes is there is not there
    2% <= E < 10%   proceed, narrowed to the affected subset
    E >= 10%    proceed as specified

An interval straddling a boundary takes the more conservative band.

Usage:  python analysis/exposure.py [--force]
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis.censoring import censored_minutes, coverage_by_hour  # noqa: E402
from analysis.events import coverage, load_outages                 # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
COHORT = ROOT / "data" / "cohort_top200.json"

# PREREGISTRATION.md §3. Asserted against that document by the test suite.
REQUIRED_DAYS = 21
REQUIRED_COVERAGE = 0.95
REQUIRED_OUTAGES = 20_000
REQUIRED_SLOT_OBSERVATIONS = 3

# Downfall_M1_Spec.md §6
BAND_KILL = 0.02
BAND_NARROW = 0.10
BOOTSTRAP = 2000
SEED = 20260821


def floor_status():
    """Progress toward PREREGISTRATION.md §3. Returns (met, rows)."""
    outages = load_outages()
    covered, span, runs = coverage()
    cov_by_hour = coverage_by_hour(runs)

    days = span / 86400 if span else 0.0
    frac = covered / span if span else 0.0
    complete = sum(1 for o in outages if o.usable_duration is not None)

    # Every hour-of-week slot needs REQUIRED_SLOT_OBSERVATIONS days on which it
    # was actually watched. M0 saw one Thursday evening; a figure built from
    # evenings would describe the evening while claiming to describe the network.
    slots = defaultdict(set)
    for h, secs in cov_by_hour.items():
        if secs >= 0.5 * 3600:
            dt = datetime.fromtimestamp(h, timezone.utc)
            slots[dt.weekday() * 24 + dt.hour].add(dt.date())
    thin = sum(1 for s in range(168) if len(slots.get(s, ())) < REQUIRED_SLOT_OBSERVATIONS)

    rows = [
        ("continuous days", days, REQUIRED_DAYS, "{:.1f}"),
        ("coverage", frac, REQUIRED_COVERAGE, "{:.1%}"),
        ("completed outages", complete, REQUIRED_OUTAGES, "{:,.0f}"),
        ("hour-of-week slots still thin", thin, 0, "{:.0f}"),
    ]
    met = (days >= REQUIRED_DAYS and frac >= REQUIRED_COVERAGE
           and complete >= REQUIRED_OUTAGES and thin == 0)
    return met, rows, outages, runs


def band_for(value):
    if value < BAND_KILL:
        return "KILL"
    if value < BAND_NARROW:
        return "NARROW"
    return "PROCEED"


def compute_exposure(outages, runs, cohort_shorts):
    rows, excluded = censored_minutes(outages, runs)
    in_cohort = [r for r in rows if r["short"] in cohort_shorts]
    if not in_cohort:
        return None, excluded

    # Days are the resampling unit, not station-hours. Station-hours inside a day
    # are heavily correlated - one long outage produces several - and treating
    # them as independent would give an interval far too narrow to be honest.
    by_day = defaultdict(list)
    for r in in_cohort:
        day = datetime.fromtimestamp(r["hour_utc"], timezone.utc).date()
        by_day[day].append(1 if r["empty_s"] > 0 else 0)

    days = sorted(by_day)
    point = float(np.mean([v for d in days for v in by_day[d]]))

    rng = np.random.default_rng(SEED)
    draws = []
    for _ in range(BOOTSTRAP):
        pick = rng.choice(len(days), len(days), replace=True)
        vals = [v for i in pick for v in by_day[days[i]]]
        if vals:
            draws.append(np.mean(vals))
    lo, hi = (float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))) \
        if draws else (float("nan"), float("nan"))

    return {"E": point, "lo": lo, "hi": hi, "station_hours": len(in_cohort),
            "days": len(days)}, excluded


def main():
    met, rows, outages, runs = floor_status()

    print("PREREGISTRATION.md §3 floor")
    for name, have, need, fmt in rows:
        ok = "met" if (have >= need if name != "hour-of-week slots still thin"
                       else have <= need) else ""
        print("  {:<32}{:>12}   need {:<10} {}".format(
            name, fmt.format(have), fmt.format(need), ok))

    if not met and "--force" not in sys.argv:
        print("\nFloor not met. No exposure figure is reported.")
        print("This is the point of the floor: a provisional number captioned")
        print("'early' is how a stopping rule gets abandoned without anyone")
        print("deciding to. Run with --force only for a dry run, whose output")
        print("is not a result and may not be quoted.")
        return 2

    cohort = json.loads(COHORT.read_text())
    shorts = set(cohort["stations"])
    print("\ncohort {} stations, sha256 {}".format(cohort["n"], cohort["sha256"][:16]))

    res, excluded = compute_exposure(outages, runs, shorts)
    if res is None:
        print("no cohort station-hours observed yet")
        return 2

    print("\nexcluded, and published beside the rate:")
    for k, v in sorted(excluded.items()):
        print("  {:<24}{:>8,}".format(k, v))

    print("\nE = share of cohort station-hours containing empty-censoring")
    print("  point estimate   {:.2%}".format(res["E"]))
    print("  95% interval     {:.2%} .. {:.2%}   ({} days, {:,} station-hours)"
          .format(res["lo"], res["hi"], res["days"], res["station_hours"]))

    b_point, b_lo = band_for(res["E"]), band_for(res["lo"])
    print("\n  band at point estimate   {}".format(b_point))
    print("  band at lower bound      {}".format(b_lo))
    if b_point != b_lo:
        print("  -> interval straddles a boundary; the CONSERVATIVE band governs: {}"
              .format(b_lo))
    print("\n  VERDICT: {}".format(b_lo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
