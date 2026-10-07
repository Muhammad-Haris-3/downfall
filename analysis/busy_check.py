"""
Does `em` hold up at the BUSY stations? An extra check, labelled as one.

WHY THIS EXISTS
---------------
§4 could only test `em` where the truth is known, and the truth is only known at
stations that never run out. Those are the quiet ones - median 452 departures
over the window against 1,748 (FINDINGS M2-T2). §5 then applied `em` everywhere,
including the top 200, where it was never tested. This narrows that gap.

THIS IS NOT §4 AND CANNOT REPLACE IT
------------------------------------
It was designed AFTER §4 and §5 results were seen. It cannot rescue a failing §4
or overturn §5; it reports how far the §4 result carries to busy stations. Its
choices are committed before it is run all the same.

THE METHOD
----------
A busy station has no clean answer overall, but it has many clean HOURS: hours
in which no `empty` outage of any kind touched it. Those hours are truth.

1. Stations: the top-200 cohort (data/cohort_top200.json), the stations E was
   measured on and the ones an operator ranks first.
2. Synthetic outages: the station's OWN fully observed empty outages, moved one
   week later (one week earlier if that leaves the window). Same station, same
   hour of the week, same minute - so the outages fall in the busy minutes, as
   real ones do, and nothing about within-hour demand is assumed. A moved outage
   is kept only if every hour it touches is clean.
3. The trips that really started inside those minutes are removed; the moved
   outages enter f. Real censoring stays as it is, so `em` is fitted on a series
   exactly as messy as production's.
4. `em` is fitted on the whole active network, as in §5.
5. Error per station over the hours carrying synthetic censoring only, where the
   truth is the real departure count. Median |error| and median signed error,
   set beside the §4 thresholds (20%, +/-10%) for reference, not as a gate.

What it cannot fix: an outage moved a week sits on a week that did not run out,
which may have been a slightly quieter week. That leans toward a quieter truth,
not a busier one.

Usage:  python analysis/busy_check.py
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis.censoring import coverage_by_hour, split_by_hour         # noqa: E402
from analysis.events import coverage, load_outages                     # noqa: E402
from analysis.ranking import build_panel                               # noqa: E402
from analysis.unconstrain import METHODS                               # noqa: E402
from analysis.validation import (MARTS, MAX_ABS_ERR, MAX_SIGNED_ERR,   # noqa: E402
                                 STATIONS, WINDOW_END, WINDOW_MONTHS,
                                 WINDOW_START, impose, merge,
                                 station_error, summarise)

ROOT = Path(__file__).resolve().parent.parent
COHORT = ROOT / "data" / "cohort_top200.json"
OUT = ROOT / "data" / "busy_check.json"
WEEK = 7 * 86400


def shift(iv):
    """One week later, or one week earlier if later leaves the window."""
    s, e = iv
    return (s + WEEK, e + WEEK) if e + WEEK <= WINDOW_END else (s - WEEK, e - WEEK)


def main():
    cohort = set(json.loads(COHORT.read_text())["stations"])
    meta = json.loads(STATIONS.read_text(encoding="utf-8"))
    short_of = {sid: m.get("short") for sid, m in meta.items()}

    df, _ = build_panel()
    cov = coverage_by_hour(coverage()[2])

    dirty, real_iv = defaultdict(set), defaultdict(list)
    for o in load_outages():
        if o.kind != "empty":
            continue
        short = short_of.get(o.station)
        if short not in cohort:
            continue
        end = o.end if o.end is not None else WINDOW_END
        if end <= WINDOW_START or o.start >= WINDOW_END:
            continue
        for h, _ in split_by_hour(max(o.start, WINDOW_START), min(end, WINDOW_END)):
            dirty[short].add(h)
        if o.start_seen and o.end_seen and o.end is not None:
            real_iv[short].append((max(o.start, WINDOW_START), min(o.end, WINDOW_END)))

    trips = pd.concat([pd.read_parquet(MARTS / "departures_{}.parquet".format(m))
                       for m in WINDOW_MONTHS], ignore_index=True)
    trips["station"] = trips["station"].astype(str)
    trips = trips[(trips["t"] >= WINDOW_START) & (trips["t"] < WINDOW_END)
                  & trips["station"].isin(cohort)]
    by_station = dict(tuple(trips.groupby("station", observed=True)["t"]))

    df = df.set_index(["station", "hour_utc"])
    df["truth"] = df["departures"]
    df["synthetic"] = 0.0
    panel_hours = set(df.index.get_level_values(1))
    used = 0
    for s in sorted(cohort & set(df.index.get_level_values(0))):
        ok = []
        for iv in map(shift, real_iv[s]):
            hrs = [h for h, _ in split_by_hour(*iv)]
            if hrs and all(h not in dirty[s] and h in panel_hours for h in hrs):
                ok.append(iv)
        ok = merge(ok)
        if not ok or s not in by_station:
            continue
        used += 1
        t = by_station[s].to_numpy()
        lost = impose(t, ok)
        removed = pd.Series((t[lost] // 3600) * 3600).value_counts()
        secs = defaultdict(float)
        for a, b in ok:
            for h, x in split_by_hour(a, b):
                secs[h] += x
        idx = [(s, h) for h in secs if (s, h) in df.index]
        for key in idx:
            h = key[1]
            df.loc[key, "synthetic"] = min(secs[h], cov[h]) / cov[h]
            df.loc[key, "departures"] -= removed.get(h, 0)
    df["empty_frac"] = np.minimum(df["empty_frac"] + df["synthetic"], 1.0)
    df = df.reset_index()

    scored = df["synthetic"] > 0
    print("busy stations     {} of {} in the cohort carry synthetic outages".format(used, len(cohort)))
    print("synthetic hours   {:,}; departures hidden {:,.0f} of {:,.0f} in them".format(
        int(scored.sum()), (df["truth"] - df["departures"])[scored].sum(),
        df["truth"][scored].sum()))
    print("\nfor reference, §4 thresholds: median |err| <= {:.0f}%, signed within +/-{:.0f}%\n"
          .format(MAX_ABS_ERR * 100, MAX_SIGNED_ERR * 100))
    print("  {:<8}{:>9}{:>15}{:>16}".format("method", "stations", "median |err|", "median signed"))
    results = {}
    f_scored = np.where(scored, df["synthetic"].to_numpy(), 0.0)
    for name, method in METHODS.items():
        r = summarise(station_error(df["truth"].to_numpy(), method(df), f_scored,
                                    df["station"].to_numpy()))
        results[name] = r
        print("  {:<8}{:>9}{:>14.1f}%{:>15.1f}%".format(
            name, r["stations_scored"], r["median_abs_pct"], r["median_signed_pct"]))

    OUT.write_text(json.dumps({"label": "extra check, designed after §4/§5 were seen",
                               "stations_used": used, "synthetic_hours": int(scored.sum()),
                               "results": results}, indent=1))
    print("-> {}".format(OUT.name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
