"""
How long does a station stay unusable?

The number decides the collection cadence, so it is estimated rather than
eyeballed - and the estimate has to survive three kinds of missing data that push
it in different directions:

  RIGHT-CENSORED  Outages still open when the log ends. We know they lasted at
                  least this long. Dropping them would throw away exactly the
                  longest ones and roughly halve the answer, so Kaplan-Meier is
                  used instead of a mean.
  NOT OBSERVED    Outages whose start or end fell in a gap between runs. These
                  carry no duration at all and are counted separately.
  TRUNCATED       The window is finite. Nothing longer than the observed span can
                  be seen to end, whatever the estimator does.

Usage:  python analysis/duration.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis.events import coverage, load_outages   # noqa: E402

PUBLISH_S = 70          # M0-T1: the feed's own cycle
MIN_FOR_REPORT = 30     # below this, a curve is noise with a shape


def kaplan_meier(events):
    """events: (duration, observed). Returns [(t, survival)] stepping down."""
    events = sorted(events)
    at_risk = len(events)
    surv = 1.0
    curve = [(0.0, 1.0)]
    i = 0
    while i < len(events):
        t = events[i][0]
        tied = [e for e in events[i:] if e[0] == t]
        deaths = sum(1 for _, obs in tied if obs)
        if deaths and at_risk:
            surv *= (1 - deaths / at_risk)
            curve.append((t, surv))
        at_risk -= len(tied)
        i += len(tied)
    return curve


def surv_at(curve, t):
    s = 1.0
    for tt, ss in curve:
        if tt <= t:
            s = ss
        else:
            break
    return s


def quantile(curve, q):
    for t, s in curve:
        if s <= 1 - q:
            return t
    return None


def main():
    outages = load_outages()
    covered, span, runs = coverage()
    if not runs:
        print("no runs recorded yet")
        return 1

    fmt = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M")
    print("window: {} .. {} UTC".format(
        fmt(min(r["start"] for r in runs)), fmt(max(r["end"] for r in runs))))
    print("coverage: {:.1f} of {:.1f} hours = {:.1f}%   across {} runs\n".format(
        covered / 3600, span / 3600, covered / span * 100 if span else 100, len(runs)))

    print("{:13}{:>9}{:>13}{:>17}".format("", "usable", "still open", "unobserved end"))
    for kind in ("empty", "full", "offline"):
        rows = [o for o in outages if o.kind == kind]
        print("  {:<11}{:>9}{:>13}{:>17}".format(
            kind,
            sum(1 for o in rows if o.usable_duration is not None),
            sum(1 for o in rows if o.end is None),
            sum(1 for o in rows if o.end is not None and not o.end_seen)))

    for kind in ("empty", "full"):
        rows = [o for o in outages if o.kind == kind and o.start_seen]
        events = []
        for o in rows:
            if o.end is None:
                # Still open: censored at however long we watched it.
                last = max(r["end"] for r in runs)
                events.append((max(last - o.start, 0), False))
            elif o.end_seen:
                events.append((o.duration, True))
            # end not seen -> no duration at all, excluded entirely

        if len(events) < MIN_FOR_REPORT:
            print("\n{}: only {} usable - not reported".format(kind.upper(), len(events)))
            continue

        curve = kaplan_meier(events)
        obs = sum(1 for _, o in events if o)
        print("\n=== {} ===  {} outages ({} ended, {} still open)".format(
            kind.upper(), len(events), obs, len(events) - obs))

        print("  share still unusable after:")
        for mins in (1, 2, 5, 10, 15, 30, 60, 120):
            print("    {:>4} min   {:>5.1f}%".format(mins, surv_at(curve, mins * 60) * 100))

        for q in (0.25, 0.5, 0.75):
            t = quantile(curve, q)
            print("  {}th percentile: {}".format(
                int(q * 100),
                "{:.1f} min".format(t / 60) if t is not None else "beyond the window"))

        print("\n  ends within one {}s publish cycle: {:.1f}%  (may never appear)".format(
            PUBLISH_S, (1 - surv_at(curve, PUBLISH_S)) * 100))
        print("  ends within 5 minutes:            {:.1f}%".format(
            (1 - surv_at(curve, 300)) * 100))
    return 0


if __name__ == "__main__":
    sys.exit(main())
