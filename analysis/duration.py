"""
How long does a station stay unusable?

The number decides the collection cadence, so it is estimated rather than
eyeballed - and the estimate has to survive three kinds of missing data that all
push it in different directions:

  RIGHT-CENSORED  Outages still open when collection stopped. We know they lasted
                  at least this long. Dropping them would throw away exactly the
                  longest ones and halve the answer, so Kaplan-Meier is used
                  instead of a plain mean.
  LEFT-OPEN       Outages already underway when we started. Their true start is
                  unknown, so they carry no duration at all.
  TRUNCATED       The window is finite. Nothing longer than the run can be
                  observed to end, whatever the estimator does.
"""

import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "shortfall.db"
PUBLISH_S = 70          # M0-T1: the feed's own cycle


def kaplan_meier(events):
    """events: (duration, observed). Returns [(t, survival)] stepping down."""
    events = sorted(events)
    n_at_risk = len(events)
    surv, curve = 1.0, [(0.0, 1.0)]
    i = 0
    while i < len(events):
        t = events[i][0]
        tied = [e for e in events[i:] if e[0] == t]
        deaths = sum(1 for _, obs in tied if obs)
        if deaths and n_at_risk:
            surv *= (1 - deaths / n_at_risk)
            curve.append((t, surv))
        n_at_risk -= len(tied)
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
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    run_end = con.execute("SELECT MAX(COALESCE(ended_wall,0)) FROM runs").fetchone()[0]
    run_start, files = con.execute(
        "SELECT started_wall, files_seen FROM runs ORDER BY started_wall DESC LIMIT 1").fetchone()
    print(f"window: {(run_end-run_start)/3600:.1f} h, {files} published files\n")

    print(f"{'':13}{'closed':>8}{'still open':>12}{'left-open':>11}{'unusable':>10}")
    for kind in ("empty", "full", "offline"):
        rows = con.execute(
            "SELECT start_ts,end_ts,left_open,end_unknown FROM outages WHERE kind=?",
            (kind,)).fetchall()
        print(f"  {kind:<11}"
              f"{sum(1 for r in rows if r[1] and not r[2] and not r[3]):>8}"
              f"{sum(1 for r in rows if r[1] is None and not r[2]):>12}"
              f"{sum(1 for r in rows if r[2]):>11}"
              f"{sum(1 for r in rows if r[3]):>10}")

    for kind in ("empty", "full"):
        rows = con.execute(
            """SELECT start_ts, end_ts FROM outages
               WHERE kind=? AND left_open=0 AND end_unknown=0""", (kind,)).fetchall()
        events = [((max(e - s, 0), True) if e is not None else (max(run_end - s, 0), False))
                  for s, e in rows]
        if len(events) < 30:
            print(f"\n{kind.upper()}: only {len(events)} usable - not reported")
            continue

        curve = kaplan_meier(events)
        obs = sum(1 for _, o in events if o)
        print(f"\n=== {kind.upper()} ===  {len(events)} outages "
              f"({obs} ended, {len(events)-obs} still open at the end)")

        print("  share still unusable after:")
        for mins in (1, 2, 5, 10, 15, 30, 60, 120):
            print(f"    {mins:>4} min   {surv_at(curve, mins*60)*100:>5.1f}%")

        for q in (0.25, 0.5, 0.75):
            t = quantile(curve, q)
            print(f"  {int(q*100)}th percentile duration: "
                  + (f"{t/60:.1f} min" if t is not None else "beyond the window"))

        print(f"\n  ended within one 70s publish cycle: "
              f"{(1-surv_at(curve, PUBLISH_S))*100:.1f}%  (may never appear at all)")
        print(f"  ended within 5 minutes:              "
              f"{(1-surv_at(curve, 300))*100:.1f}%  (what a 5-min cadence would blur)")


if __name__ == "__main__":
    main()
