"""
Turn a month of raw trips into per-station, per-hour counts.

Three things this file is careful about, because all three are silent when wrong:

TIME ZONE. Trip timestamps are naive local New York time. The live feed's
`last_reported` is a UTC epoch. Counting demand in local hours and availability
in UTC hours would misalign every join by four or five hours, and the result
would look perfectly reasonable. Everything is converted to UTC here, once, and
the local hour is carried alongside only for human-facing labels.

MEMORY. A month is up to 5.4M trips across six CSVs. Loading all of it at once
costs several gigabytes in pandas object columns for no benefit, since the output
is bounded by stations x hours rather than by trips. Each member is aggregated
alone and the small results are summed - so peak memory is set by the largest
single CSV (~1M rows), not by the month.

ZEROS. A station-hour with no trips is not stored. Absent means zero - but only
for a station that existed and was open in that hour. Which stations those are is
a separate question this file does not answer.

Usage:
  python pipeline/aggregate_trips.py 202607              # fetch, aggregate, delete
  python pipeline/aggregate_trips.py data/202602.zip     # aggregate a local file
"""

import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
BUCKET = "https://s3.amazonaws.com/tripdata/"
LOCAL_TZ = "America/New_York"
COLS = ["started_at", "ended_at", "start_station_id", "end_station_id",
        "member_casual", "rideable_type"]


def download(month: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "{}.zip".format(month)
    if dest.exists():
        return dest
    url = "{}{}-citibike-tripdata.zip".format(BUCKET, month)
    print("  downloading {}".format(url), flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "downfall/1.0"})
    with urllib.request.urlopen(req, timeout=600) as r, dest.open("wb") as fh:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
    print("  got {:.0f} MB".format(dest.stat().st_size / 1e6), flush=True)
    return dest


def to_utc(series: pd.Series, dropped: dict, label: str) -> pd.Series:
    """Naive New York local -> UTC. Impossible/ambiguous clock times become NaT."""
    naive = pd.to_datetime(series, errors="coerce")
    bad_parse = int(naive.isna().sum())

    # DST: 02:30 on a spring-forward date does not exist, and 01:30 on a
    # fall-back date happens twice. Both are dropped and counted rather than
    # shifted, because a shifted timestamp is a fabricated one.
    local = naive.dt.tz_localize(LOCAL_TZ, ambiguous="NaT", nonexistent="NaT")
    dst_lost = int(local.isna().sum()) - bad_parse

    dropped[label + "_unparseable"] = dropped.get(label + "_unparseable", 0) + bad_parse
    dropped[label + "_dst_ambiguous"] = dropped.get(label + "_dst_ambiguous", 0) + dst_lost
    return local.dt.tz_convert("UTC")


def aggregate_member(df: pd.DataFrame, dropped: dict) -> pd.DataFrame:
    """One CSV's worth of trips -> station-hour counts. Never sees the others."""
    df["dep_utc"] = to_utc(df["started_at"], dropped, "started_at")
    df["arr_utc"] = to_utc(df["ended_at"], dropped, "ended_at")
    for c in ("start_station_id", "end_station_id"):
        df[c] = df[c].str.strip()

    # Departures and arrivals are counted independently. A trip with a usable
    # start and an unusable end still tells us a bike LEFT, and discarding the
    # whole row would quietly understate demand at the busiest stations.
    dep = df.loc[df["dep_utc"].notna() & df["start_station_id"].notna()
                 & (df["start_station_id"] != ""),
                 ["start_station_id", "dep_utc", "member_casual", "rideable_type"]]
    dep = dep.rename(columns={"start_station_id": "station"})
    dep["hour_utc"] = dep["dep_utc"].dt.floor("h")
    # Flags precomputed as integers so the grouping is a plain sum. A lambda
    # here runs once per group and turns a 20-second job into a 20-minute one.
    dep["departures"] = 1
    dep["dep_member"] = (dep["member_casual"] == "member").astype("int32")
    dep["dep_ebike"] = (dep["rideable_type"] == "electric_bike").astype("int32")
    g_dep = (dep.groupby(["station", "hour_utc"], sort=False)
                [["departures", "dep_member", "dep_ebike"]].sum())

    arr = df.loc[df["arr_utc"].notna() & df["end_station_id"].notna()
                 & (df["end_station_id"] != ""), ["end_station_id", "arr_utc"]]
    arr = arr.rename(columns={"end_station_id": "station"})
    arr["hour_utc"] = arr["arr_utc"].dt.floor("h")
    g_arr = arr.groupby(["station", "hour_utc"], sort=False).size().rename("arrivals")

    return g_dep.join(g_arr, how="outer").fillna(0).astype("int64")


def main(target: str, out_dir: str = None):
    out = Path(out_dir) if out_dir else ROOT / "data" / "marts"
    out.mkdir(parents=True, exist_ok=True)

    if target.endswith(".zip"):
        zip_path, month, fetched = Path(target), Path(target).stem.split("-")[0], False
    else:
        zip_path, month, fetched = download(target, ROOT / "data" / "raw"), target, True

    print("aggregating {}".format(month), flush=True)
    z = zipfile.ZipFile(zip_path)
    members = sorted(n for n in z.namelist()
                     if n.endswith(".csv") and not n.startswith("__MACOSX"))

    dropped, n_raw, parts = {}, 0, []
    for n in members:
        with z.open(n) as f:
            df = pd.read_csv(io.TextIOWrapper(f, encoding="utf-8", errors="replace"),
                             usecols=COLS, dtype=str)
        n_raw += len(df)
        parts.append(aggregate_member(df, dropped))
        del df
        print("    {}: {:,} rows -> {:,} station-hours".format(
            n, n_raw, len(parts[-1])), flush=True)
    z.close()

    # Sum the per-member aggregates. Each is already tiny; the sum is bounded by
    # stations x hours in the month, whatever the trip count was.
    counts = (pd.concat(parts).groupby(level=["station", "hour_utc"]).sum()
                .astype("int32").reset_index())
    del parts

    # Local labels for humans. Derived from UTC, never parsed a second time.
    local = counts["hour_utc"].dt.tz_convert(LOCAL_TZ)
    counts["hour_local"] = local.dt.hour.astype("int8")
    counts["dow_local"] = local.dt.dayofweek.astype("int8")
    counts["date_local"] = local.dt.date.astype("str")

    path = out / "trip_counts_{}.parquet".format(month)
    counts.to_parquet(path, index=False, compression="zstd")

    manifest = {
        "month": month,
        "source_file": zip_path.name,
        "source_members": members,
        "rows_raw": n_raw,
        "dropped": dropped,
        "departures_counted": int(counts["departures"].sum()),
        "arrivals_counted": int(counts["arrivals"].sum()),
        "station_hours": len(counts),
        "distinct_stations": int(counts["station"].nunique()),
        "utc_span": [str(counts["hour_utc"].min()), str(counts["hour_utc"].max())],
        "output": path.name,
        "output_bytes": path.stat().st_size,
    }
    (out / "manifest_{}.json".format(month)).write_text(json.dumps(manifest, indent=2))

    if fetched:
        zip_path.unlink()          # 22.5 GB across the archive; nothing is kept

    print("\n  raw trips            {:,}".format(n_raw))
    print("  dropped              {}".format(dropped))
    print("  departures counted   {:,}".format(manifest["departures_counted"]))
    print("  arrivals counted     {:,}".format(manifest["arrivals_counted"]))
    print("  station-hours stored {:,}".format(len(counts)))
    print("  -> {}  ({:.1f} MB)".format(path, path.stat().st_size / 1e6))
    return manifest


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
