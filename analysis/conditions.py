"""
What weather and time of week actually do to ridership.

THE TRAP THIS FILE IS BUILT AROUND
----------------------------------
The obvious calculation is: average trips in wet hours, average trips in dry
hours, take the ratio. It is also wrong, and wrong by a lot, because rain is not
randomly assigned across the year or the day.

  - Wet hours are more common in some months than others, and ridership swings
    by a factor of four between January and July.
  - It rains at 3am as often as at 6pm, but those hours carry wildly different
    numbers of riders.

So a naive comparison charges rain for the season and for the hour. The fix is
not a cleverer model - it is comparing like with like: rainy and dry hours from
the SAME month and the SAME hour of the week, and only from cells that contain
both.

THE DIRECTION OF THE BIAS WAS PREDICTED WRONG, AND IS RECORDED HERE
-------------------------------------------------------------------
This file was written expecting the naive figure to OVERSTATE the effect of
rain - the reasoning being that wet hours would be over-represented at quiet
times, so some of the shortfall would really be the quietness.

The measurement says the reverse. Naive: -30.2%. Like-for-like: -35.8%. The
naive number is too SMALL, and correcting it makes rain look worse.

The likely reason, unverified: New York's rain is disproportionately summer
convective rain, and summer carries roughly four times the ridership of winter.
So wet hours are drawn from the busy end of the year, which flatters them.

Recorded rather than quietly fixed, because the useful lesson is not "control
for confounders" - everybody says that. It is that the direction a confounder
pushes is not reliably guessable, so a naive number cannot be treated as a
conservative one just because it feels like it should be.

Usage:  python analysis/conditions.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MARTS = ROOT / "data" / "marts"
OUT = ROOT / "web" / "public" / "data" / "conditions.json"

WINDOW = ["202401", "202402", "202403", "202404", "202405", "202406",
          "202407", "202408", "202409", "202410", "202411", "202412",
          "202501", "202502", "202503", "202504", "202505", "202506",
          "202507", "202508", "202509", "202510", "202511", "202512",
          "202601", "202602", "202603", "202604", "202605", "202606", "202607"]

WET_MM = 0.2       # below this is drizzle the radar sees and a rider does not
SEED = 20260821
BOOTSTRAP = 2000


def network_hours():
    """Departures across the whole network, per UTC hour."""
    frames = []
    for m in WINDOW:
        p = MARTS / "trip_counts_{}.parquet".format(m)
        if p.exists():
            frames.append(pd.read_parquet(
                p, columns=["hour_utc", "departures", "hour_local", "dow_local"]))
    df = pd.concat(frames, ignore_index=True)
    g = df.groupby("hour_utc", as_index=False).agg(
        trips=("departures", "sum"),
        hour_local=("hour_local", "first"),
        dow_local=("dow_local", "first"),
    )
    # dow_local is int8 in the marts; 6*24 overflows it and Saturday lands on
    # -112. Widened before arithmetic, for the same reason as M2-T0.
    g["how"] = g["dow_local"].astype("int32") * 24 + g["hour_local"].astype("int32")
    g["ym"] = g["hour_utc"].dt.strftime("%Y%m")
    return g


def stratified_ratio(df, mask, rng):
    """Wet-vs-dry ratio, comparing only within (month, hour-of-week) cells.

    Returns (ratio, lo, hi, cells, hours). Cells lacking either condition are
    dropped - they cannot contribute a comparison, and including their level
    would smuggle the confounding back in through the mean.
    """
    d = df.copy()
    d["wet"] = mask
    cells = []
    for _, cell in d.groupby(["ym", "how"], sort=False):
        wet = cell.loc[cell["wet"], "trips"]
        dry = cell.loc[~cell["wet"], "trips"]
        if len(wet) == 0 or len(dry) == 0 or dry.mean() == 0:
            continue
        cells.append((wet.mean(), dry.mean(), len(wet) + len(dry)))
    if not cells:
        return None
    arr = np.array(cells)

    def ratio_of(rows):
        # Weighted by hours in the cell: a cell built on 40 observations should
        # not count the same as one built on 2.
        w = rows[:, 2]
        return float((rows[:, 0] * w).sum() / (rows[:, 1] * w).sum())

    point = ratio_of(arr)
    draws = [ratio_of(arr[rng.integers(0, len(arr), len(arr))])
             for _ in range(BOOTSTRAP)]
    return (point, float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975)),
            len(arr), int(arr[:, 2].sum()))


def main():
    print("loading network hours")
    g = network_hours()
    w = pd.read_parquet(MARTS / "weather_hourly.parquet")
    df = g.merge(w, on="hour_utc", how="inner")
    print("  {:,} hours matched to weather".format(len(df)))

    rng = np.random.default_rng(SEED)
    wet = df["precip_mm"] >= WET_MM

    # --- the naive number, computed so it can be shown to be wrong ----------
    naive = float(df.loc[wet, "trips"].mean() / df.loc[~wet, "trips"].mean())

    # --- the same comparison, like for like --------------------------------
    strat = stratified_ratio(df, wet, rng)

    print("\nRAIN")
    print("  naive ratio, wet vs dry hours          {:.3f}  ({:+.1f}%)".format(
        naive, (naive - 1) * 100))
    print("  same month and hour-of-week            {:.3f}  ({:+.1f}%)".format(
        strat[0], (strat[0] - 1) * 100))
    print("  95% interval                           {:.3f} .. {:.3f}".format(
        strat[1], strat[2]))
    print("  {:,} comparable cells, {:,} hours".format(strat[3], strat[4]))

    # --- temperature, by band, within hour-of-week -------------------------
    bands = [(-99, 0), (0, 5), (5, 10), (10, 15), (15, 20),
             (20, 25), (25, 30), (30, 99)]
    dry = df[~wet]           # temperature measured on dry hours only, so the
                             # cold effect is not partly a rain effect
    base = dry.groupby("how")["trips"].transform("mean")
    dry = dry.assign(rel=dry["trips"] / base.replace(0, np.nan))
    temp_rows = []
    for lo, hi in bands:
        sel = dry[(dry["temp_c"] >= lo) & (dry["temp_c"] < hi)]
        if len(sel) < 50:
            continue
        temp_rows.append({"lo": lo if lo > -99 else None, "hi": hi if hi < 99 else None,
                          "rel": round(float(sel["rel"].mean()), 4),
                          "hours": int(len(sel))})
    print("\nTEMPERATURE (dry hours only, relative to that hour-of-week's average)")
    for r in temp_rows:
        label = "{} to {} C".format(r["lo"] if r["lo"] is not None else "<0",
                                    r["hi"] if r["hi"] is not None else "30+")
        print("  {:<14} {:>6.2f}x   {:>7,} hours".format(label, r["rel"], r["hours"]))

    # --- weekday vs weekend shape ------------------------------------------
    prof = df.groupby(["how"])["trips"].mean()
    weekday = [float(prof.get(d * 24 + h, 0)) for d in range(5) for h in range(24)]
    weekday = [float(np.mean(weekday[h::24])) for h in range(24)]
    weekend = [float(np.mean([prof.get(d * 24 + h, 0) for d in (5, 6)]))
               for h in range(24)]

    payload = {
        "window": [WINDOW[0], WINDOW[-1]],
        "hours_matched": len(df),
        "wet_threshold_mm": WET_MM,
        "rain": {
            "naive": round(naive, 4),
            "stratified": round(strat[0], 4),
            "lo": round(strat[1], 4), "hi": round(strat[2], 4),
            "cells": strat[3], "hours": strat[4],
        },
        "temperature": temp_rows,
        "weekday_by_hour": [round(x, 1) for x in weekday],
        "weekend_by_hour": [round(x, 1) for x in weekend],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1))
    print("\n  -> {}".format(OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
