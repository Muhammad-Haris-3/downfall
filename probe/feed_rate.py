"""
M0-T1 - How fast does the Citi Bike feed actually refresh?

We poll station_status.json on a fixed tick and write down, for every station,
the timestamp the feed itself claims the reading was taken (`last_reported`).

The gap between two DIFFERENT values of `last_reported` for the same station is
the feed's real refresh interval. Polling faster than that returns a value we
already have, so this number - not our patience - sets the finest interval in
which a stockout can be observed.

Raw polls are kept so the measurement can be re-derived without collecting again.
"""

import gzip
import json
import sys
import time
import urllib.request
from pathlib import Path

FEED = "https://gbfs.lyft.com/gbfs/1.1/bkn/en/station_status.json"
OUT = Path(__file__).resolve().parent.parent / "data" / "feed_rate_raw.jsonl.gz"

# Fields worth keeping. Everything else in the payload is static or unused here.
KEEP = ("num_bikes_available", "num_ebikes_available", "num_docks_available",
        "num_bikes_disabled", "num_docks_disabled", "last_reported")


def poll():
    """One read of the feed. Returns (our clock, {station_id: fields})."""
    req = urllib.request.Request(FEED, headers={"User-Agent": "downfall-probe/0.1"})
    with urllib.request.urlopen(req, timeout=20) as r:
        payload = json.load(r)
    wall = time.time()
    stations = {
        s["station_id"]: [s.get(k) for k in KEEP]
        for s in payload["data"]["stations"]
    }
    return wall, stations


def main(minutes: float, tick: float):
    deadline = time.time() + minutes * 60
    n = 0
    OUT.parent.mkdir(parents=True, exist_ok=True)

    with gzip.open(OUT, "wt", encoding="utf-8") as fh:
        # Header line records the run's own parameters, so the file explains itself.
        fh.write(json.dumps({"kind": "header", "feed": FEED, "fields": KEEP,
                             "tick_s": tick, "planned_minutes": minutes}) + "\n")
        while time.time() < deadline:
            started = time.time()
            try:
                wall, stations = poll()
            except Exception as exc:                      # a failed poll is data too
                fh.write(json.dumps({"kind": "error", "wall": time.time(),
                                     "error": repr(exc)}) + "\n")
                print(f"  poll {n}: FAILED {exc}", flush=True)
            else:
                fh.write(json.dumps({"kind": "poll", "wall": wall,
                                     "stations": stations}) + "\n")
                n += 1
                if n % 6 == 0:
                    left = int(deadline - time.time())
                    print(f"  {n} polls, {len(stations)} stations, {left}s left", flush=True)

            # Sleep the remainder of the tick, never a fixed amount, so a slow
            # request does not drag the whole schedule later and later.
            time.sleep(max(0.0, tick - (time.time() - started)))

    print(f"done: {n} polls -> {OUT} ({OUT.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main(minutes=float(sys.argv[1]) if len(sys.argv) > 1 else 10.0,
         tick=float(sys.argv[2]) if len(sys.argv) > 2 else 10.0)
