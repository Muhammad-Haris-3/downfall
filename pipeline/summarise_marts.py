"""
Report what the marts contain, from their manifests alone.

Used two ways: as a human-readable check after aggregation, and as the commit
subject the aggregation workflow writes. The commit history doubles as the
provenance log, so this is the part of the record most people will read.

It reads manifests, never the parquet. A mart whose manifest disagrees with it
is a mart we cannot account for, and that is worth surfacing separately rather
than papering over by recomputing.

Usage:
  python pipeline/summarise_marts.py
  python pipeline/summarise_marts.py --commit-message
"""

import json
import sys
from pathlib import Path

MARTS = Path(__file__).resolve().parent.parent / "data" / "marts"


def load():
    out = []
    for p in sorted(MARTS.glob("manifest_*.json")):
        out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


def totals(ms):
    return {
        "months": len(ms),
        "raw": sum(m["rows_raw"] for m in ms),
        "dep": sum(m["departures_counted"] for m in ms),
        "arr": sum(m["arrivals_counted"] for m in ms),
        "station_hours": sum(m["station_hours"] for m in ms),
        "bytes": sum(m["output_bytes"] for m in ms),
        "dropped": sum(sum(m["dropped"].values()) for m in ms),
    }


def main():
    ms = load()
    if not ms:
        print("no marts")
        return 0
    t = totals(ms)

    if "--commit-message" in sys.argv:
        print("Aggregate: {} months, {:.1f}M trips, {:.0f} MB of counts".format(
            t["months"], t["raw"] / 1e6, t["bytes"] / 1e6))
        print()
        print("{} .. {}   {:,} departures, {:,} arrivals, {:,} station-hours".format(
            ms[0]["month"], ms[-1]["month"], t["dep"], t["arr"], t["station_hours"]))
        if t["dropped"]:
            print()
            print("{:,} rows dropped on the way in; see each manifest for the breakdown"
                  .format(t["dropped"]))
        return 0

    print("{:8}{:>12}{:>14}{:>14}{:>10}".format(
        "month", "raw trips", "departures", "station-hrs", "MB"))
    for m in ms:
        print("{:8}{:>12,}{:>14,}{:>14,}{:>10.1f}".format(
            m["month"], m["rows_raw"], m["departures_counted"],
            m["station_hours"], m["output_bytes"] / 1e6))
    print("\n{} months   {:,} trips   {:,} station-hours   {:.0f} MB".format(
        t["months"], t["raw"], t["station_hours"], t["bytes"] / 1e6))

    # A departure that never became an arrival is a trip that ended nowhere
    # identifiable. Small and expected; a jump would not be.
    gap = t["dep"] - t["arr"]
    print("departures - arrivals: {:,} ({:.2f}%)".format(gap, gap / t["dep"] * 100))
    if t["dropped"]:
        print("rows dropped on the way in: {:,} ({:.3f}%)".format(
            t["dropped"], t["dropped"] / t["raw"] * 100))
    return 0


if __name__ == "__main__":
    sys.exit(main())
