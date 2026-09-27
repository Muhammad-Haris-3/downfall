"""
PREREGISTRATION.md §4 - mark the estimator where the answer is already known.

This is the run the pre-registration fixes, not the preliminary one in
`validate_estimator.py`. It decides whether the project's central claim stands:
**if it fails, the claim is withdrawn, not caveated.** Everything below that a
result could be steered by is therefore decided here, in code committed before
the run, and not after looking.

THE PROCEDURE, as §4 states it, and how each step is done
---------------------------------------------------------
1. Stations with zero recorded stockout minutes over the analysis window.
     No `empty` outage of any kind overlaps the window - including ones with an
     unobserved start or end, and ones still open. A partly seen outage is
     still proof the station ran out. The station must have capacity and be
     active: at least one departure per window day, on average, so that a dock
     nobody uses does not qualify by default. M1 spec §6 requires at least 100
     such stations, and below that this refuses to run.

2. Impose the observed outage pattern of a matched station that does run out.
     Donors are active stations with at least one fully observed `empty` outage
     in the window. Each never-stockout station takes the nearest donor on
     capacity and log departures, both z-scored - exactly the two variables §4
     names, neither of which the estimator uses. With replacement: a donor
     can lend its pattern to several stations.

     The donor's outages are imposed on the SAME calendar minutes they happened,
     and the trips the held-out station actually made during those minutes are
     removed. This is why the archive's trip-level start times are needed: the
     preliminary test thinned hourly counts at random, which assumes demand is
     even within the hour - the assumption `scaled` is built on. Here nothing is
     assumed; the removed trips are the ones that really happened then.

     Only fully observed outages are imposed, which is also all production uses
     to compute f (analysis/censoring.py). Hours watched for under half their
     length are dropped, as in production.

3. Estimate demand from the censored series.
     The estimator judged is `em`, fixed here before the run. `scaled` and
     `naive` are reported beside it as the comparisons from M2-T0, and neither
     can rescue a failing `em`. It is fitted on the censored series alone: the
     held-out stations, every usable hour in the window.

4. Compare with the true, uncensored figure.
     One error per station: its estimated departures summed over its censored
     hours, against the true departures in those same hours. Uncensored hours
     are excluded because every method returns them unchanged, and counting
     them would dilute the error toward zero. A station whose censored hours
     held no true departures has no percentage error; it is counted and
     reported, not scored.

PASS requires both, for `em`: median |error| <= 20%, median signed error
within +/-10%.

Usage:  python analysis/validation.py
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis.censoring import MIN_COVERAGE, coverage_by_hour, split_by_hour  # noqa: E402
from analysis.events import coverage, load_outages                            # noqa: E402
from analysis.unconstrain import METHODS                                      # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MARTS = ROOT / "data" / "marts"
STATIONS = ROOT / "data" / "stations.json"
OUT = ROOT / "data" / "validation_s4.json"
LOCAL_TZ = "America/New_York"

# The analysis window: collection start to the end of the last month whose
# trips are needed. Fixed before the run.
WINDOW_START = int(datetime(2026, 8, 20, tzinfo=timezone.utc).timestamp())
WINDOW_END = int(datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp())
WINDOW_MONTHS = ["202608", "202609"]

# PREREGISTRATION.md §4, and M1 spec §6 condition 2.
MAX_ABS_ERR = 0.20
MAX_SIGNED_ERR = 0.10
MIN_COHORT = 100
JUDGED = "em"


def merge(intervals):
    """Sort and merge overlapping [start, end) intervals."""
    out = []
    for s, e in sorted(intervals):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [tuple(x) for x in out]


def impose(times, intervals):
    """Boolean mask: which departure times fall inside any [start, end) interval.

    `times` sorted or not; `intervals` as returned by merge().
    """
    if len(intervals) == 0:
        return np.zeros(len(times), dtype=bool)
    starts = np.array([s for s, _ in intervals])
    ends = np.array([e for _, e in intervals])
    i = np.searchsorted(starts, times, side="right") - 1
    return (i >= 0) & (times < ends[np.maximum(i, 0)])


def station_error(truth, est, f, station):
    """Per-station signed percentage error over censored hours. None if no truth there."""
    out = {}
    df = pd.DataFrame({"s": station, "t": truth, "e": est, "c": f > 0})
    g = df[df["c"]].groupby("s")[["t", "e"]].sum()
    for s, r in g.iterrows():
        out[s] = None if r["t"] <= 0 else float((r["e"] - r["t"]) / r["t"])
    return out


def summarise(errors):
    pe = np.array([v for v in errors.values() if v is not None])
    return {"stations_scored": int(len(pe)),
            "stations_unscorable": int(sum(v is None for v in errors.values())),
            "median_abs_pct": float(np.median(np.abs(pe)) * 100),
            "median_signed_pct": float(np.median(pe) * 100)}


def passes(s):
    return (s["median_abs_pct"] <= MAX_ABS_ERR * 100
            and abs(s["median_signed_pct"]) <= MAX_SIGNED_ERR * 100)


def main():
    missing = [m for m in WINDOW_MONTHS
               if not (MARTS / "departures_{}.parquet".format(m)).exists()]
    if missing:
        print("trip start times not yet aggregated for {}.".format(", ".join(missing)))
        print("The window runs to {} and §4 is run once, on all of it.".format(
            datetime.fromtimestamp(WINDOW_END, timezone.utc).date()))
        return 2

    meta = json.loads(STATIONS.read_text(encoding="utf-8"))
    short_of = {sid: m.get("short") for sid, m in meta.items()}
    cap_of = {m["short"]: m.get("cap") for m in meta.values() if m.get("short")}

    trips = pd.concat([pd.read_parquet(MARTS / "departures_{}.parquet".format(m))
                       for m in WINDOW_MONTHS], ignore_index=True)
    trips["station"] = trips["station"].astype(str)
    trips = trips[(trips["t"] >= WINDOW_START) & (trips["t"] < WINDOW_END)]
    dep_total = trips.groupby("station").size()
    days = (WINDOW_END - WINDOW_START) / 86400
    active = {s for s, n in dep_total.items() if n >= days and (cap_of.get(s) or 0) > 0}

    # ---- step 1 and the donor pool, from the outage record
    ever_empty, donor_iv = set(), defaultdict(list)
    for o in load_outages():
        if o.kind != "empty":
            continue
        end = o.end if o.end is not None else WINDOW_END
        if end <= WINDOW_START or o.start >= WINDOW_END:
            continue
        short = short_of.get(o.station)
        ever_empty.add(short)
        if o.start_seen and o.end_seen:
            donor_iv[short].append((max(o.start, WINDOW_START), min(end, WINDOW_END)))

    held = sorted(active - ever_empty)
    donors = sorted(s for s in active if donor_iv.get(s))
    print("analysis window   {} .. {}".format(
        datetime.fromtimestamp(WINDOW_START, timezone.utc).date(),
        datetime.fromtimestamp(WINDOW_END, timezone.utc).date()))
    print("never-stockout    {} active stations (need {})".format(len(held), MIN_COHORT))
    print("donors            {} stations with a fully observed empty outage".format(len(donors)))

    # M1-T7: the extrapolation gap, visible rather than assumed away.
    rest = sorted(active - set(held))
    gap = {k: {"capacity_median": float(np.median([cap_of[s] for s in grp])),
               "departures_median": float(np.median([dep_total[s] for s in grp]))}
           for k, grp in (("never_stockout", held), ("rest", rest)) if grp}
    for k, v in gap.items():
        print("  {:<16} median capacity {:>5.0f}   median departures {:>7,.0f}".format(
            k, v["capacity_median"], v["departures_median"]))

    if len(held) < MIN_COHORT:
        print("\nNever-stockout cohort below {}. §4 cannot be run as specified "
              "(M1 spec §6), and this is reported rather than worked around.".format(MIN_COHORT))
        OUT.write_text(json.dumps({"verdict": "NOT RUN", "reason": "cohort too small",
                                   "never_stockout": len(held), "gap": gap}, indent=1))
        return 1

    # ---- step 2: match, then censor
    def features(ss):
        return np.column_stack([[cap_of[s] for s in ss],
                                [np.log1p(dep_total[s]) for s in ss]]).astype(float)
    pool = np.vstack([features(held), features(donors)])
    mu, sd = pool.mean(0), pool.std(0)
    zh, zd = (features(held) - mu) / sd, (features(donors) - mu) / sd
    match = {h: donors[int(np.argmin(((zd - zh[i]) ** 2).sum(1)))]
             for i, h in enumerate(held)}

    _, _, runs = coverage()
    cov = coverage_by_hour(runs)
    hours = np.array(sorted(h for h, s in cov.items()
                            if WINDOW_START <= h < WINDOW_END and s >= MIN_COVERAGE * 3600))
    hour_set = set(hours.tolist())

    by_station = dict(tuple(trips[trips["station"].isin(held)].groupby("station")["t"]))
    rows = []
    for h in held:
        iv = merge(donor_iv[match[h]])
        t = by_station[h].to_numpy()
        lost = impose(t, iv)
        hour_of = (t // 3600) * 3600
        truth = pd.Series(hour_of).value_counts()
        seen = pd.Series(hour_of[~lost]).value_counts()
        empty = defaultdict(float)
        for s, e in iv:
            for hh, secs in split_by_hour(s, e):
                empty[hh] += secs
        for hh in hours:
            rows.append((h, hh, int(truth.get(hh, 0)), int(seen.get(hh, 0)),
                         min(empty.get(hh, 0.0), cov[hh]) / cov[hh]))
    df = pd.DataFrame(rows, columns=["station", "hour_utc", "truth", "departures", "empty_frac"])
    local = pd.to_datetime(df["hour_utc"], unit="s", utc=True).dt.tz_convert(LOCAL_TZ)
    df["hour_local"] = local.dt.hour.astype("int32")
    df["dow_local"] = local.dt.dayofweek.astype("int32")
    assert set(df["hour_utc"].unique()) <= hour_set

    censored = df["empty_frac"] > 0
    print("station-hours     {:,}, of which censored {:,} ({:.1%})".format(
        len(df), int(censored.sum()), censored.mean()))
    print("departures hidden {:,} of {:,}".format(
        int((df["truth"] - df["departures"]).sum()), int(df["truth"].sum())))

    # ---- steps 3 and 4
    print("\nthresholds: median |err| <= {:.0f}%, median signed within +/-{:.0f}%, "
          "judged on `{}`\n".format(MAX_ABS_ERR * 100, MAX_SIGNED_ERR * 100, JUDGED))
    print("  {:<8}{:>9}{:>15}{:>16}".format("method", "stations", "median |err|", "median signed"))
    results = {}
    for name, method in METHODS.items():
        s = summarise(station_error(df["truth"].to_numpy(), method(df),
                                    df["empty_frac"].to_numpy(), df["station"].to_numpy()))
        s["passes"] = passes(s)
        results[name] = s
        print("  {:<8}{:>9}{:>14.1f}%{:>15.1f}%   {}".format(
            name, s["stations_scored"], s["median_abs_pct"], s["median_signed_pct"],
            ("PASS" if s["passes"] else "fail") + ("   <- judged" if name == JUDGED else "")))

    verdict = "PASS" if results[JUDGED]["passes"] else "FAIL"
    print("\nVERDICT: {}".format(verdict))
    if verdict == "FAIL":
        print("PREREGISTRATION.md §4: the central claim is withdrawn, not caveated.")

    OUT.write_text(json.dumps({
        "verdict": verdict, "judged": JUDGED,
        "window": [WINDOW_START, WINDOW_END],
        "never_stockout": len(held), "donors": len(donors), "gap": gap,
        "station_hours": len(df), "censored_hours": int(censored.sum()),
        "thresholds": {"median_abs": MAX_ABS_ERR, "median_signed": MAX_SIGNED_ERR},
        "results": results,
        "matches": match,
    }, indent=1))
    print("-> {}".format(OUT.name))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
