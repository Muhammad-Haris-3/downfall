"""
Turn the marts into the data the site reads.

The site is static. There is no API and no database, because neither would do
anything a build step cannot: the trip archive changes once a month, and the
outage record changes hourly but is committed to this repository anyway. A
served query would be a served query against a file we already have.

Two outputs, split by who reads them:

  web/public/data/network.json   downloaded by the browser, for the map. Kept
                                 small - one row per station, no profiles.
  web/data/profiles.json         read at BUILD time only, to generate each
                                 station page. Never shipped to a browser, so
                                 its size is a build concern and not a page one.

WHAT THIS FILE MAY AND MAY NOT SAY
----------------------------------
Everything here is OBSERVED demand: departures that happened. That is precisely
the quantity the project exists to argue is wrong, so nothing exported here is
labelled "demand" without qualification - EXCEPT the `est` block, which is
written only when data/validation_s4.json says PASS and data/ranking_s5.json
exists. Both are read, never recomputed here: the site shows the run that was
committed, not a fresh one that could quietly differ from it.

Usage:  python pipeline/export_web.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from analysis.censoring import censored_minutes, coverage_by_hour   # noqa: E402
from analysis.exposure import REQUIRED_DAYS, floor_status           # noqa: E402
MARTS = ROOT / "data" / "marts"
STATIONS = ROOT / "data" / "stations.json"
COHORT = ROOT / "data" / "cohort_top200.json"
VALIDATION = ROOT / "data" / "validation_s4.json"
RANKING = ROOT / "data" / "ranking_s5.json"
PUBLIC = ROOT / "web" / "public" / "data"
BUILD = ROOT / "web" / "data"

# The twelve complete months preceding collection - the same window the cohort
# was fixed on, so the map and the cohort describe the same period.
WINDOW = ["202508", "202509", "202510", "202511", "202512",
          "202601", "202602", "202603", "202604", "202605", "202606", "202607"]


def load_window():
    frames = []
    for m in WINDOW:
        p = MARTS / "trip_counts_{}.parquet".format(m)
        if not p.exists():
            print("  missing {}, skipping".format(p.name))
            continue
        frames.append(pd.read_parquet(
            p, columns=["station", "departures", "arrivals",
                        "hour_local", "dow_local"]))
    if not frames:
        raise SystemExit("no marts found")
    return pd.concat(frames, ignore_index=True)


def hour_of_week(df):
    """0-167, Monday 00:00 = 0.

    dow_local is int8 in the marts. 6 * 24 = 144 overflows int8 and Saturday
    lands on -112, which np.bincount refuses - the only reason the same bug was
    caught in M2-T0 rather than silently folding Saturday into Wednesday. Widened
    here for the same reason.
    """
    return df["dow_local"].astype("int32") * 24 + df["hour_local"].astype("int32")


def hours_empty():
    """Hours each station spent with no bikes, over the §3 window.

    Returns (by_short, window) or (None, None) while the floor is unmet: the
    pre-registration forbids publishing a stockout figure before it holds, so
    the card stays blank rather than showing a number captioned "early".
    Only outages with both ends observed count, as in every duration figure.
    """
    met, _, outages, runs, _ = floor_status()
    if not met:
        return None, None
    now = max(r["end"] for r in runs)
    start = now - REQUIRED_DAYS * 86400
    in_window = [r for r in runs if r["end"] > start]
    rows, _ = censored_minutes(outages, in_window)
    by_short = {}
    for r in rows:
        if r["short"] and r["hour_utc"] >= start:
            by_short[r["short"]] = by_short.get(r["short"], 0.0) + r["empty_s"]
    watched = sum(s for h, s in coverage_by_hour(in_window).items() if h >= start)
    window = {
        "from": datetime.fromtimestamp(start, timezone.utc).date().isoformat(),
        "to": datetime.fromtimestamp(now, timezone.utc).date().isoformat(),
        "watched_h": round(watched / 3600),
    }
    return {k: round(v / 3600, 1) for k, v in by_short.items()}, window


def estimates():
    """The §5 per-station estimate, or (None, None) unless §4 passed.

    The estimate covers the §4 window (six weeks), not the twelve months the
    map's departures come from, so it travels with its own observed count and
    its own ranks. Setting six-week estimated demand beside twelve-month
    departures would make every station look under-counted by a factor of eight.
    """
    if not (VALIDATION.exists() and RANKING.exists()):
        return None, None
    if json.loads(VALIDATION.read_text()).get("verdict") != "PASS":
        return None, None
    r = json.loads(RANKING.read_text())
    by_short = {p["short"]: {"obs": p["departures"], "est": round(p["estimated"]),
                             "r_obs": p["rank_naive"], "r_est": p["rank_est"],
                             "cens_h": p["censored_h"]}
                for p in r["per_station"]}
    meta = {"from": datetime.fromtimestamp(r["window"][0], timezone.utc).date().isoformat(),
            "to": datetime.fromtimestamp(r["window"][1] - 1, timezone.utc).date().isoformat(),
            "stations": r["stations"]}
    return by_short, meta


def main():
    PUBLIC.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)

    print("reading {} months".format(len(WINDOW)))
    df = load_window()
    print("  {:,} station-hours".format(len(df)))

    meta = json.loads(STATIONS.read_text()) if STATIONS.exists() else {}
    # The live feed keys by station_id; the trip archive keys by short_name.
    # short_name is the bridge (FINDINGS M0-T4) and identity is dated, so a
    # station renamed since the window will simply not resolve - which is
    # counted below rather than quietly dropped.
    by_short = {}
    for sid, m in meta.items():
        if m.get("short"):
            by_short[m["short"]] = dict(m, station_id=sid)

    cohort = set(json.loads(COHORT.read_text())["stations"]) if COHORT.exists() else set()

    df["how"] = hour_of_week(df)
    totals = df.groupby("station").agg(
        departures=("departures", "sum"),
        arrivals=("arrivals", "sum"),
        active_hours=("departures", "size"),
    )

    # All 2,500 weekly profiles in two passes, not one filtered scan per station.
    # The obvious loop - `df[df.station == short]` inside a loop over stations -
    # is O(stations x rows) and took minutes on 20M rows. Encoding (station,
    # hour-of-week) as a single integer and letting bincount do the work is one
    # pass over the data. Same shape of mistake as the lambda groupby in M0-T5.
    codes, uniques = pd.factorize(df["station"], sort=False)
    flat = codes.astype("int64") * 168 + df["how"].to_numpy("int64")
    size = len(uniques) * 168
    dep_all = np.bincount(flat, weights=df["departures"].to_numpy(), minlength=size)
    arr_all = np.bincount(flat, weights=df["arrivals"].to_numpy(), minlength=size)
    dep_all = dep_all.reshape(len(uniques), 168).astype("int64")
    arr_all = arr_all.reshape(len(uniques), 168).astype("int64")
    index_of = {s: i for i, s in enumerate(uniques)}

    empty, window = hours_empty()
    print("  hours empty: " + ("floor not met, left blank" if window is None
                               else "{from} to {to}".format(**window)))

    est, est_window = estimates()
    print("  estimate: " + ("§4 not passed, left blank" if est is None
                            else "{from} to {to}".format(**est_window)))

    network, profiles, unresolved = [], {}, 0
    for short, row in totals.iterrows():
        info = by_short.get(short)
        if info is None or info.get("lat") is None:
            unresolved += 1
            continue
        i = index_of[short]
        prof_dep, prof_arr = dep_all[i], arr_all[i]

        network.append({
            "s": short,
            "n": info.get("name"),
            "lat": round(float(info["lat"]), 5),
            "lon": round(float(info["lon"]), 5),
            "cap": info.get("cap"),
            # `dep` is departures RECORDED, not demand. The distinction is the
            # entire project, so the field is not named `demand`.
            "dep": int(row["departures"]),
            "arr": int(row["arrivals"]),
            "top200": short in cohort,
        })
        if window is not None:
            # A station never seen empty has no row, and that is a measured 0.
            network[-1]["empty_h"] = empty.get(short, 0.0)
            network[-1]["watched_h"] = window["watched_h"]
        if est is not None and short in est:
            network[-1]["est"] = est[short]
        profiles[short] = {
            "dep": [int(x) for x in prof_dep],
            "arr": [int(x) for x in prof_arr],
        }

    network.sort(key=lambda r: -r["dep"])
    for i, r in enumerate(network):
        r["rank"] = i + 1

    payload = {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window": [WINDOW[0], WINDOW[-1]],
        "stations": len(network),
        "unresolved_stations": unresolved,
        "total_departures": int(totals["departures"].sum()),
        # Named so a reader cannot mistake it for a demand estimate.
        "measure": "departures recorded in the public trip archive",
        "caveat": ("Observed departures understate demand at any station that "
                   "ran out of bikes. Correcting for that is the project's "
                   "subject and no correction is applied here."),
        "outage_window": window,
        "estimate_window": est_window,
        "network": network,
    }
    (PUBLIC / "network.json").write_text(json.dumps(payload, separators=(",", ":")))
    (BUILD / "profiles.json").write_text(json.dumps(profiles, separators=(",", ":")))

    print("  {:,} stations exported, {} unresolved".format(len(network), unresolved))
    print("  network.json  {:.1f} MB (browser)".format(
        (PUBLIC / "network.json").stat().st_size / 1e6))
    print("  profiles.json {:.1f} MB (build only)".format(
        (BUILD / "profiles.json").stat().st_size / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
