"""
Shortfall collector - records when stations stop being usable, and when they recover.

Design follows M0-T1: the feed republishes every 70 seconds, so we poll on that
cadence and use `If-None-Match` to skip files we already hold. Timestamps come
from the feed's own `last_reported`, never our wall clock, because our clock is
~122s behind the reading anyway and the feed's is internally consistent.

Only state CHANGES are written. See schema.sql for why.

Usage:  python collect.py [minutes]      (0 or omitted = run until stopped)
"""

import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "shortfall.db"
STATUS = "https://gbfs.lyft.com/gbfs/1.1/bkn/en/station_status.json"
INFO = "https://gbfs.lyft.com/gbfs/1.1/bkn/en/station_information.json"

POLL_S = 35          # half the 70s publish cycle, so a new file is caught promptly
UA = {"User-Agent": "shortfall-collector/0.1 (portfolio research project)"}
BROKEN_TS = 1_700_000_000   # last_reported below this is the 1970 placeholder


def fetch(url, etag=None):
    """Returns (payload, etag) or (None, etag) when unchanged."""
    headers = dict(UA)
    if etag:
        headers["If-None-Match"] = etag
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.load(r), r.headers.get("ETag")
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return None, etag
        raise


def classify(s):
    """The station's state right now, or None if it cannot be judged."""
    if not s.get("is_installed") or not s.get("is_renting"):
        return "offline"
    if s.get("num_bikes_available", 0) == 0:
        return "empty"
    if s.get("num_docks_available", 0) == 0:
        return "full"
    return None            # usable


def load_stations(con, run_ts):
    info, _ = fetch(INFO)
    rows = [(s["station_id"], s.get("name"), s.get("lat"), s.get("lon"),
             s.get("capacity"), run_ts, run_ts)
            for s in info["data"]["stations"]]
    con.executemany(
        """INSERT INTO stations (station_id,name,lat,lon,capacity,first_seen,last_seen)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(station_id) DO UPDATE SET
             name=excluded.name, lat=excluded.lat, lon=excluded.lon,
             capacity=excluded.capacity, last_seen=excluded.last_seen""", rows)
    con.commit()
    return len(rows)


def main(minutes=0.0):
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.executescript((Path(__file__).parent / "schema.sql").read_text())

    run_id = uuid.uuid4().hex[:12]
    started = int(time.time())
    con.execute("INSERT INTO runs (run_id, started_wall) VALUES (?,?)", (run_id, started))
    con.commit()

    n_st = load_stations(con, started)
    print(f"run {run_id}: {n_st} stations known", flush=True)

    # Any outage left open by a previous run belongs to that run's coverage, not
    # ours. Adopt them, but they stay left_open so their duration is never used.
    open_now = {(sid, kind): oid for oid, sid, kind in
                con.execute("SELECT id, station_id, kind FROM outages WHERE end_ts IS NULL")}
    adopted = set(open_now)
    if adopted:
        print(f"adopted {len(adopted)} outages left open by an earlier run", flush=True)

    etag = None
    first_file = True
    files = reqs = nomod = errs = 0
    deadline = started + minutes * 60 if minutes else None

    try:
        while deadline is None or time.time() < deadline:
            tick = time.time()
            try:
                payload, etag = fetch(STATUS, etag)
                reqs += 1
            except Exception as exc:
                errs += 1
                print(f"  error: {exc!r}", flush=True)
            else:
                if payload is None:
                    nomod += 1
                else:
                    files += 1
                    opened, closed = step(con, payload, run_id, open_now,
                                          first_file, adopted)
                    first_file = False
                    if files % 20 == 0 or opened or closed:
                        print(f"  file {files}  +{opened} outages  -{closed} recovered"
                              f"  (open: {len(open_now)})", flush=True)

            con.execute("""UPDATE runs SET files_seen=?, requests=?, not_modified=?,
                                  errors=?, ended_wall=? WHERE run_id=?""",
                        (files, reqs, nomod, errs, int(time.time()), run_id))
            con.commit()
            time.sleep(max(0.0, POLL_S - (time.time() - tick)))
    except KeyboardInterrupt:
        print("stopped by hand", flush=True)

    con.execute("UPDATE runs SET ended_wall=? WHERE run_id=?", (int(time.time()), run_id))
    con.commit()
    con.close()
    print(f"run {run_id} ended: {files} files, {nomod} unchanged, {errs} errors", flush=True)


def step(con, payload, run_id, open_now, first_file, adopted=frozenset()):
    """Compare this file against what we believe is open, and record the deltas."""
    opened = closed = 0
    seen = set()

    for s in payload["data"]["stations"]:
        sid = s["station_id"]
        ts = s.get("last_reported") or 0
        if ts < BROKEN_TS:          # M0-T1: 87 stations carry a 1970 placeholder
            continue
        state = classify(s)
        if state:
            seen.add((sid, state))
            key = (sid, state)
            if key not in open_now:
                cur = con.execute(
                    """INSERT INTO outages (station_id, kind, start_ts, start_run, left_open)
                       VALUES (?,?,?,?,?)""",
                    (sid, state, ts, run_id, 1 if first_file else 0))
                open_now[key] = cur.lastrowid
                opened += 1
            # A station cannot be empty and full at once; states are exclusive by
            # construction in classify(), so nothing else needs closing here.

    # Anything we held open that this file no longer reports has recovered.
    now_ts = max((s.get("last_reported") or 0) for s in payload["data"]["stations"])
    for key in [k for k in open_now if k not in seen]:
        # An outage inherited from an earlier run and already over by our first
        # file ended at some point inside the collection gap. We know that it
        # ended, and nothing more. Stamping it with `now_ts` would invent a
        # duration, so it is flagged and excluded from duration work instead.
        unknown = 1 if (first_file and key in adopted) else 0
        con.execute("UPDATE outages SET end_ts=?, end_run=?, end_unknown=? WHERE id=?",
                    (now_ts, run_id, unknown, open_now.pop(key)))
        closed += 1

    con.commit()
    return opened, closed


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 0.0)
