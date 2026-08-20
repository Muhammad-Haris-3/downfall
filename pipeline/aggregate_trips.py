"""
Turn a month of raw trips into per-station, per-hour counts.

Two things this file is careful about, because both are silent when wrong:

TIME ZONE. Trip timestamps are naive local New York time. The live feed's
`last_reported` is a UTC epoch. Counting demand in local hours and availability
in UTC hours would misalign every join by four or five hours, and the result
would look perfectly reasonable. Everything is converted to UTC here, once, and
the local hour is carried alongside only for human-facing labels.

ZEROS. A station-hour with no trips is not stored. Absent means zero - but only
for a station that existed and was open in that hour. Which stations those are
is a separate question this file does not answer, so it records the station's
first and last observed activity in the manifest rather than implying a network
that never changes.

Usage:  python aggregate_trips.py <month.zip> [out_dir]
"""

import io
import json
import sys
import zipfile
from pathlib import Path

import pandas as pd

LOCAL_TZ = "America/New_York"
COLS = ["started_at", "ended_at", "start_station_id", "end_station_id",
        "member_casual", "rideable_type"]


def read_month(zip_path: Path) -> pd.DataFrame:
    z = zipfile.ZipFile(zip_path)
    names = [n for n in z.namelist()
             if n.endswith(".csv") and not n.startswith("__MACOSX")]
    frames = []
    for n in sorted(names):
        with z.open(n) as f:
            frames.append(pd.read_csv(io.TextIOWrapper(f, encoding="utf-8",
                                                       errors="replace"),
                                      usecols=COLS, dtype=str))
        print(f"  read {n}: {len(frames[-1]):,} rows", flush=True)
    return pd.concat(frames, ignore_index=True)


def to_utc(series: pd.Series, dropped: dict, label: str) -> pd.Series:
    """Naive New York local -> UTC. Impossible/ambiguous clock times become NaT."""
    naive = pd.to_datetime(series, errors="coerce")
    bad_parse = int(naive.isna().sum())

    # DST: 02:30 on a spring-forward date does not exist, and 01:30 on a
    # fall-back date happens twice. Both are dropped and counted rather than
    # shifted, because a shifted timestamp is a fabricated one.
    local = naive.dt.tz_localize(LOCAL_TZ, ambiguous="NaT", nonexistent="NaT")
    dst_lost = int(local.isna().sum()) - bad_parse

    dropped[f"{label}_unparseable"] = bad_parse
    dropped[f"{label}_dst_ambiguous"] = dst_lost
    return local.dt.tz_convert("UTC")


def main(zip_path: str, out_dir: str = "data/marts"):
    zip_path = Path(zip_path)
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    month = zip_path.stem.split("-")[0]

    print(f"aggregating {zip_path.name}")
    df = read_month(zip_path)
    n_raw = len(df)

    dropped = {}
    df["dep_utc"] = to_utc(df["started_at"], dropped, "started_at")
    df["arr_utc"] = to_utc(df["ended_at"], dropped, "ended_at")

    df["start_station_id"] = df["start_station_id"].str.strip()
    df["end_station_id"] = df["end_station_id"].str.strip()

    # Departures and arrivals are counted independently. A trip with a usable
    # start and an unusable end still tells us a bike LEFT, and discarding the
    # whole row would quietly understate demand at the busiest stations.
    dep = df.loc[df["dep_utc"].notna() & df["start_station_id"].notna()
                 & (df["start_station_id"] != ""),
                 ["start_station_id", "dep_utc", "member_casual", "rideable_type"]]
    dep = dep.rename(columns={"start_station_id": "station"})
    dep["hour_utc"] = dep["dep_utc"].dt.floor("h")

    arr = df.loc[df["arr_utc"].notna() & df["end_station_id"].notna()
                 & (df["end_station_id"] != ""), ["end_station_id", "arr_utc"]]
    arr = arr.rename(columns={"end_station_id": "station"})
    arr["hour_utc"] = arr["arr_utc"].dt.floor("h")

    # Flags precomputed as integers so the grouping is a plain sum. A lambda
    # here runs once per group and turns a 20-second job into a 20-minute one.
    dep["is_member"] = (dep["member_casual"] == "member").astype("int32")
    dep["is_ebike"] = (dep["rideable_type"] == "electric_bike").astype("int32")
    dep["one"] = 1
    g_dep = (dep.groupby(["station", "hour_utc"], sort=False)[["one", "is_member", "is_ebike"]]
                .sum()
                .rename(columns={"one": "departures", "is_member": "dep_member",
                                 "is_ebike": "dep_ebike"}))
    g_arr = arr.groupby(["station", "hour_utc"], sort=False).size().rename("arrivals")

    counts = g_dep.join(g_arr, how="outer").fillna(0).astype("int32").reset_index()

    # Local labels for humans. Derived from UTC, never parsed a second time.
    local = counts["hour_utc"].dt.tz_convert(LOCAL_TZ)
    counts["hour_local"] = local.dt.hour.astype("int8")
    counts["dow_local"] = local.dt.dayofweek.astype("int8")
    counts["date_local"] = local.dt.date.astype("str")

    path = out / f"trip_counts_{month}.parquet"
    counts.to_parquet(path, index=False, compression="zstd")

    manifest = {
        "month": month,
        "source_file": zip_path.name,
        "rows_raw": n_raw,
        "dropped": dropped,
        "departures_counted": int(counts["departures"].sum()),
        "arrivals_counted": int(counts["arrivals"].sum()),
        "station_hours": len(counts),
        "distinct_stations": int(counts["station"].nunique()),
        "utc_span": [str(counts["hour_utc"].min()), str(counts["hour_utc"].max())],
        "output": str(path),
        "output_bytes": path.stat().st_size,
    }
    (out / f"manifest_{month}.json").write_text(json.dumps(manifest, indent=2))

    print(f"\n  raw trips            {n_raw:,}")
    print(f"  dropped              {dropped}")
    print(f"  departures counted   {manifest['departures_counted']:,}")
    print(f"  arrivals counted     {manifest['arrivals_counted']:,}")
    print(f"  station-hours stored {len(counts):,}")
    print(f"  -> {path}  ({path.stat().st_size/1e6:.1f} MB)")
    return manifest


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "data/marts")
