"""
PREREGISTRATION.md §5 - does correcting for censoring change the ranking?

§4 passed (data/validation_s4.json): `em` recovers hidden departures to a median
10.8% with no lean. This is the test that question was a gate for. Like §4 it is
run ONCE, and every choice that could steer it is fixed below and committed
before the run.

WHAT §5 FIXES
-------------
Stations ranked twice - by observed departures and by estimated true demand. The
claim stands only if rank change is positively associated with censored exposure
at p < 0.01, one-sided, and the effect size in rank positions per censored hour
is THE finding. A significant but tiny effect is a null result.

WHAT §5 LEAVES OPEN, AND IS DECIDED HERE BEFORE THE RUN
-------------------------------------------------------
Window.     The §4 window, 2026-08-20 to 2026-10-01. Trip start times exist for
            exactly those months, and an estimator validated on a window is
            applied to that window.
Stations.   Active as §4 defines it: capacity > 0 and at least one departure per
            window day on average. A dock nobody uses has no rank worth moving.
Hours.      Every hour watched for at least half its length (censoring.py). A
            station-hour that was offline throughout leaves the data - offline
            censors nothing, it is a station that was not there.
Censoring.  f = fully observed `empty` time / observed time, exactly as
            production computes it. An empty outage with an unobserved boundary
            contributes no f, so its hour enters as if uncensored with its low
            count - which biases the estimate DOWN and the test against the claim.
Estimate.   `em`, the estimator §4 judged. Nothing else is ranked.
Rank.       1 = most demand. Rank change = naive rank - estimated rank, so a
            station that moves UP the list has a POSITIVE change.
Exposure.   Censored hours per station: the sum of f over its usable hours, i.e.
            hours of observed empty time.
Effect.     OLS slope of rank change on censored hours, in positions per hour.
p-value.    One-sided permutation test of that slope, 10,000 shuffles of exposure
            across stations, fixed seed. Not the OLS p-value: ranks are not
            independent observations and the textbook formula assumes they are.
            Spearman's rho is reported beside it.

A NOTE THAT MUST TRAVEL WITH THE RESULT
---------------------------------------
`em` never lowers an hour: it adds the expected rate times f to what was
observed. So a station with more censoring gains more estimated demand by
construction, and the DIRECTION of the association is close to guaranteed. The
p-value is therefore a weak gate here and the effect size carries the result -
which is what §5 already says. What is not guaranteed is how far stations move,
and whether the list an operator would act on - the top of it - changes at all.
The turnover of the top 50, 100 and 200 is reported for that reason.

§5 does not define "tiny". No threshold is invented here after the fact. The
slope is reported with what it means in positions for a typical and a heavily
censored station, and the reader can judge it.

§4 was validated on never-stockout stations, which are quieter (median 452
departures over the window against 1,748). Applying `em` to busy stations is an
extrapolation, and this result inherits it.

Usage:  python analysis/ranking.py
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis.censoring import MIN_COVERAGE, coverage_by_hour, split_by_hour  # noqa: E402
from analysis.events import coverage, load_outages                            # noqa: E402
from analysis.unconstrain import em                                           # noqa: E402
from analysis.validation import (LOCAL_TZ, MARTS, STATIONS, WINDOW_END,       # noqa: E402
                                 WINDOW_MONTHS, WINDOW_START)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "ranking_s5.json"
VALIDATION = ROOT / "data" / "validation_s4.json"
ALPHA = 0.01
PERMUTATIONS = 10_000
SEED = 20261007
TOP_N = (50, 100, 200)


def rank_desc(x):
    """1 = largest. Ties share the average rank, so a tie cannot fake a move."""
    return pd.Series(x).rank(ascending=False, method="average").to_numpy()


def slope(x, y):
    xc = x - x.mean()
    return float((xc * (y - y.mean())).sum() / (xc ** 2).sum())


def permutation_p(x, y, n, seed):
    """One-sided: share of shuffles whose slope is at least the observed one."""
    rng = np.random.default_rng(seed)
    obs = slope(x, y)
    xc = x - x.mean()
    yc = y - y.mean()
    denom = (xc ** 2).sum()
    hits = sum((rng.permutation(xc) * yc).sum() / denom >= obs for _ in range(n))
    return (hits + 1) / (n + 1)        # never report an exact zero


def build_panel():
    meta = json.loads(STATIONS.read_text(encoding="utf-8"))
    short_of = {sid: m.get("short") for sid, m in meta.items()}
    cap_of = {m["short"]: m.get("cap") for m in meta.values() if m.get("short")}

    trips = pd.concat([pd.read_parquet(MARTS / "departures_{}.parquet".format(m))
                       for m in WINDOW_MONTHS], ignore_index=True)
    trips["station"] = trips["station"].astype(str)
    trips = trips[(trips["t"] >= WINDOW_START) & (trips["t"] < WINDOW_END)]
    days = (WINDOW_END - WINDOW_START) / 86400
    totals = trips.groupby("station").size()
    active = sorted(s for s, n in totals.items() if n >= days and (cap_of.get(s) or 0) > 0)

    _, _, runs = coverage()
    cov = coverage_by_hour(runs)
    hours = np.array(sorted(h for h, s in cov.items()
                            if WINDOW_START <= h < WINDOW_END and s >= MIN_COVERAGE * 3600))

    empty_s, offline_s = defaultdict(float), defaultdict(float)
    for o in load_outages():
        if o.end is None or not (o.start_seen and o.end_seen) or o.kind == "full":
            continue
        short = short_of.get(o.station)
        acc = empty_s if o.kind == "empty" else offline_s
        for h, secs in split_by_hour(max(o.start, WINDOW_START), min(o.end, WINDOW_END)):
            acc[(short, h)] += secs

    trips = trips[trips["station"].isin(active)]
    counts = trips.assign(h=(trips["t"] // 3600) * 3600).groupby(["station", "h"]).size()

    st = np.repeat(active, len(hours))
    hh = np.tile(hours, len(active))
    covered = np.array([cov[h] for h in hours])[np.tile(np.arange(len(hours)), len(active))]
    off = np.array([offline_s.get((s, h), 0.0) for s, h in zip(st, hh)])
    emp = np.array([empty_s.get((s, h), 0.0) for s, h in zip(st, hh)])
    df = pd.DataFrame({"station": st, "hour_utc": hh,
                       "empty_frac": np.minimum(emp, covered) / covered})
    df["departures"] = counts.reindex(pd.MultiIndex.from_arrays([st, hh])).fillna(0).to_numpy()
    df = df[off < covered].reset_index(drop=True)
    local = pd.to_datetime(df["hour_utc"], unit="s", utc=True).dt.tz_convert(LOCAL_TZ)
    df["hour_local"] = local.dt.hour.astype("int32")
    df["dow_local"] = local.dt.dayofweek.astype("int32")
    return df, len(hours)


def main():
    v = json.loads(VALIDATION.read_text()) if VALIDATION.exists() else {}
    if v.get("verdict") != "PASS":
        print("§4 has not passed. §5 is not run: there is no validated estimate to rank by.")
        return 2
    if OUT.exists() and "--again" not in sys.argv:
        print("§5 has already been run - see {}. It is run once.".format(OUT.name))
        return 0

    df, n_hours = build_panel()
    df["estimated"] = em(df)

    g = df.groupby("station").agg(departures=("departures", "sum"),
                                  estimated=("estimated", "sum"),
                                  censored_h=("empty_frac", "sum"),
                                  hours=("hour_utc", "size"))
    g["rank_naive"] = rank_desc(g["departures"])
    g["rank_est"] = rank_desc(g["estimated"])
    g["rank_change"] = g["rank_naive"] - g["rank_est"]

    x = g["censored_h"].to_numpy(float)
    y = g["rank_change"].to_numpy(float)
    b = slope(x, y)
    p = permutation_p(x, y, PERMUTATIONS, SEED)
    rho = float(pd.Series(x).rank().corr(pd.Series(y).rank()))
    supported = p < ALPHA and b > 0

    turnover = {}
    for n in TOP_N:
        a = set(g.nsmallest(n, "rank_naive").index)
        e = set(g.nsmallest(n, "rank_est").index)
        turnover[n] = len(e - a)

    med_x, p90_x = float(np.median(x)), float(np.quantile(x, 0.9))
    hidden = float(g["estimated"].sum() - g["departures"].sum())

    print("window            2026-08-20 .. 2026-10-01, {} usable hours".format(n_hours))
    print("stations ranked   {:,}".format(len(g)))
    print("station-hours     {:,}, censored {:,} ({:.1%})".format(
        len(df), int((df["empty_frac"] > 0).sum()), (df["empty_frac"] > 0).mean()))
    print("departures        observed {:,.0f}   estimated {:,.0f}   hidden {:,.0f} ({:.1%})".format(
        g["departures"].sum(), g["estimated"].sum(), hidden, hidden / g["departures"].sum()))
    print("\nEFFECT  {:+.2f} rank positions per censored hour".format(b))
    print("  a median station ({:.0f} censored h) moves {:+.0f}; one at the 90th "
          "percentile ({:.0f} h) moves {:+.0f}, relative to an uncensored one".format(
              med_x, b * med_x, p90_x, b * p90_x))
    print("  permutation p (one-sided, {:,})  {:.4g}   Spearman rho {:.3f}".format(
        PERMUTATIONS, p, rho))
    print("  stations moving 10+ places: up {}, down {}".format(
        int((y >= 10).sum()), int((y <= -10).sum())))
    for n in TOP_N:
        print("  top {:<4} by estimated demand not in top {} by departures: {}".format(
            n, n, turnover[n]))
    print("\n§5 {}".format("SUPPORTED at p < 0.01 - the effect size is the finding"
                          if supported else "NOT SUPPORTED"))

    per = g.sort_values("rank_est")
    OUT.write_text(json.dumps({
        "supported": supported, "estimator": "em",
        "window": [WINDOW_START, WINDOW_END], "usable_hours": n_hours,
        "stations": int(len(g)), "station_hours": int(len(df)),
        "observed": float(g["departures"].sum()), "estimated": float(g["estimated"].sum()),
        "effect_positions_per_censored_hour": b, "p_one_sided": p,
        "permutations": PERMUTATIONS, "seed": SEED, "spearman_rho": rho,
        "censored_hours_median": med_x, "censored_hours_p90": p90_x,
        "top_n_turnover": turnover,
        "per_station": [{"short": s, "departures": int(r.departures),
                         "estimated": round(float(r.estimated), 1),
                         "censored_h": round(float(r.censored_h), 2),
                         "rank_naive": float(r.rank_naive), "rank_est": float(r.rank_est)}
                        for s, r in per.iterrows()],
    }, indent=1))
    print("-> {}".format(OUT.name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
