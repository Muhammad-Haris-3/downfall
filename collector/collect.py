"""
Downfall collector - records when a station stops being usable, and when it recovers.

WHY AN EVENT LOG AND NOT A TABLE
--------------------------------
An outage opens in one hourly job and usually closes in a later one. Storing a
row and editing it when it closes would mean rewriting history on every run, and
"append-only" would be a promise made by careful code rather than a property of
the store.

So nothing is ever rewritten. Two events are appended - `open` when a station
stops being usable, `close` when it recovers - and an outage is the pair. The
file is append-only by construction, and git history is the audit trail: any
edit to a past line shows up as a diff in a public commit.

CADENCE (from FINDINGS M0-T1 and M0-T6)
---------------------------------------
The feed republishes every 70s and declares `ttl: 60`. We poll at 60s: no faster
than the publisher asks, still strictly faster than publication, so no file is
skipped. Timestamps come from the feed's own `last_reported`, so noticing a file
late shifts nothing.

Usage:  python collector/collect.py [minutes]     (0 = until stopped)
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVENTS = ROOT / "data" / "events"
STATE = ROOT / "data" / "state" / "open.json"
HEARTBEAT = ROOT / "data" / "state" / "collector.json"
RUNS = ROOT / "data" / "runs.ndjson"
STATIONS = ROOT / "data" / "stations.json"

STATUS = "https://gbfs.lyft.com/gbfs/1.1/bkn/en/station_status.json"
INFO = "https://gbfs.lyft.com/gbfs/1.1/bkn/en/station_information.json"

POLL_S = 60
BROKEN_TS = 1_700_000_000     # M0-T1: 87 stations carry a 1970 placeholder
SKIP_GAP_S = 100              # two published files further apart than this = a skip
UA = {"User-Agent": "downfall-collector/1.0 (+https://github.com/Muhammad-Haris-3/downfall)"}


# ---------------------------------------------------------------- feed access

def fetch(url, etag=None):
    headers = dict(UA)
    if etag:
        headers["If-None-Match"] = etag
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r), r.headers.get("ETag")
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return None, etag
        raise


def classify(s):
    """The station's state, or None when it is usable.

    Order matters. A station that is switched off reports zero bikes, and
    counting that as a stockout would invent scarcity that does not exist.
    """
    if not s.get("is_installed") or not s.get("is_renting"):
        return "offline"
    if s.get("num_bikes_available", 0) == 0:
        return "empty"
    if s.get("num_docks_available", 0) == 0:
        return "full"
    return None


# ------------------------------------------------------------- durable state

def state_from_log():
    """Rebuild the set of open outages by replaying the event log.

    The log is the record; `open.json` is a cache of it. They are written at
    different moments, and the cache is the one that goes stale: a new job
    checks the repository out while its predecessor is still finishing, so it
    can start from a state file up to a checkpoint old. Every outage that opened
    in that window is missing from it, the new run writes a second `open`, and
    the pair reads afterwards as a lost close - 620 of them, 2.9% of all
    outages, before this existed.

    Replaying 42,000 events costs well under a second, and the log cannot
    disagree with itself.
    """
    open_now = {}
    for p in sorted(EVENTS.glob("*.ndjson")):
        try:
            with p.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith(("<<<<<<<", "=======", ">>>>>>>")):
                        continue
                    ev = json.loads(line)
                    key = (ev["st"], ev["k"])
                    if ev["ev"] == "open":
                        open_now[key] = {"since": ev["ts"], "run": ev.get("run"),
                                         "o": ev.get("o", 0)}
                    else:
                        open_now.pop(key, None)
        except (OSError, ValueError):
            # A damaged log is not a reason to start blind; fall back to the
            # cache, which at worst is stale rather than unreadable.
            return None
    return open_now


def load_state():
    """Open outages carried over from the previous run.

    The log wins when the two disagree, because the cache is the thing that goes
    stale. The cache is still read, and a disagreement is reported rather than
    silently resolved - it is the signal that a handover dropped something.
    """
    cached = {}
    if STATE.exists():
        raw = json.loads(STATE.read_text())
        cached = {tuple(k.split("|", 1)): v for k, v in raw.items()}

    replayed = state_from_log()
    if replayed is None:
        return cached

    only_log = set(replayed) - set(cached)
    only_cache = set(cached) - set(replayed)
    if only_log or only_cache:
        print("  state: {} open per log, {} per cache "
              "({} only in log, {} only in cache) - using the log".format(
                  len(replayed), len(cached), len(only_log), len(only_cache)),
              flush=True)
    return replayed


def count_events_on_disk():
    """Lines currently in the event log. Cheap, and the baseline for the guard."""
    n = 0
    for p in sorted(EVENTS.glob("*.ndjson")):
        with p.open("rb") as fh:
            n += sum(1 for line in fh if line.strip())
    return n


def write_heartbeat(run_id, expected_total, written, started):
    """What the collector believes is on disk, for the checkpoint to check.

    The orphaned-handle bug (FINDINGS M1-T8b) was invisible precisely because
    nothing ever compared the collector's own count against the file it was
    supposedly writing. Recording the expectation is what turns a silent loss
    into a failed job.

    `started` is here so that coverage can credit a run that is still going. A
    run writes its coverage row only when it ends - counting it twice was the
    reason for that rule - but a run lasts up to 350 minutes, so for most of any
    moment the newest run has recorded nothing and coverage reads low by up to
    one run length. `at` bounds the credit: an abandoned run stops accruing the
    moment it stops writing.
    """
    HEARTBEAT.parent.mkdir(parents=True, exist_ok=True)
    tmp = HEARTBEAT.with_suffix(".tmp")
    tmp.write_text(json.dumps({"run": run_id, "expected_events_on_disk": expected_total,
                               "written_this_run": written, "at": int(time.time()),
                               "started": started}))
    tmp.replace(HEARTBEAT)


def save_state(open_now):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps({k[0] + "|" + k[1]: v for k, v in open_now.items()}))
    tmp.replace(STATE)            # atomic: a killed job never leaves half a file


def event_path(observed_at):
    day = datetime.fromtimestamp(observed_at, timezone.utc).strftime("%Y-%m-%d")
    return EVENTS / (day + ".ndjson")


class EventLog:
    """Append-only, and re-opened by NAME on every write.

    Filed by the day we OBSERVED the event, never by the event's own timestamp.
    A station that stopped reporting in May still carries `last_reported` from
    May, and filing by that scattered a single hour of collection across a dozen
    historical files - rewriting months of history on every run, which is the one
    thing an append-only log must not do.

    WHY IT RE-OPENS EVERY TIME, INSTEAD OF HOLDING A HANDLE
    ------------------------------------------------------
    It used to keep one handle open for the life of the run. That silently threw
    away five hours of collection.

    The job checkpoints every 30 minutes, and the checkpoint ran
    `git pull --rebase --autostash`. Git does not edit a file in place: it writes
    a new one and renames it over the old. On Linux the old inode is then
    unlinked, but a process holding it open keeps writing to it happily - to a
    file with no name, which nothing will ever read and which vanishes when the
    process exits.

    The collector went on running. `save_state` survived, because it opens a
    fresh file for every write, so the state file kept updating and the
    checkpoint kept reporting success with a frozen event count. Nothing failed.
    See FINDINGS M1-T8b.

    Opening by name for each write costs one syscall a minute and cannot be
    orphaned, because the name is resolved at write time rather than at open
    time.
    """

    def __init__(self):
        self.path = None
        self.n = 0
        self._pending = []

    def append(self, ev):
        self.path = event_path(time.time())
        self._pending.append(json.dumps(ev, separators=(",", ":")) + "\n")
        self.n += 1

    def flush(self):
        """Write everything buffered, to the file that has this NAME right now."""
        if not self._pending:
            return
        p = self.path
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write("".join(self._pending))
            fh.flush()
            os.fsync(fh.fileno())
        self._pending = []

    def close(self):
        self.flush()


# ---------------------------------------------------------------- station meta

def refresh_stations():
    """Station metadata changes slowly; fetched once per run, kept as one file."""
    info, _ = fetch(INFO)
    rows = {}
    for s in info["data"]["stations"]:
        rows[s["station_id"]] = {
            "short": s.get("short_name"), "name": s.get("name"),
            "lat": s.get("lat"), "lon": s.get("lon"), "cap": s.get("capacity"),
        }
    STATIONS.parent.mkdir(parents=True, exist_ok=True)
    prev = json.loads(STATIONS.read_text()) if STATIONS.exists() else {}
    changed = rows != prev
    if changed:
        STATIONS.write_text(json.dumps(rows, indent=0, sort_keys=True))
    return len(rows), changed


# ------------------------------------------------------------------- stepping

def step(payload, log, open_now, run_id, first_file, starts_uncertain=False):
    """One published file: what changed since the last one we held.

    `starts_uncertain` marks opens seen on the first file as left-censored - the
    outage was already underway before we could see it begin. True on a cold
    start, and after a long gap, where an outage may have been running for hours.
    Not true on a normal handover: a minute of gap is inside the feed's own
    reporting noise, so the start is as well known as any other.
    """
    opened = closed = gapclosed = 0
    seen = set()
    latest = 0

    for s in payload["data"]["stations"]:
        ts = s.get("last_reported") or 0
        if ts < BROKEN_TS:
            continue
        latest = max(latest, ts)
        state = classify(s)
        if not state:
            continue
        key = (s["station_id"], state)
        seen.add(key)
        if key not in open_now:
            ev = {"ev": "open", "st": key[0], "k": state, "ts": ts, "run": run_id}
            if first_file and starts_uncertain:
                ev["o"] = 1          # already underway; start is a lower bound
            log.append(ev)
            open_now[key] = {"since": ts, "run": run_id, "o": ev.get("o", 0)}
            opened += 1

    for key in [k for k in open_now if k not in seen]:
        # An outage we inherited that is already over by our first file ended at
        # an unknown moment inside the gap between runs. Recording `latest` as
        # its end would invent a duration, so it is flagged and excluded from
        # duration work rather than guessed at.
        unknown = first_file and open_now[key].get("run") != run_id
        ev = {"ev": "close", "st": key[0], "k": key[1], "ts": latest, "run": run_id}
        if unknown:
            ev["u"] = 1
            gapclosed += 1
        log.append(ev)
        del open_now[key]
        closed += 1

    return opened, closed, gapclosed


# ----------------------------------------------------------------------- main

HANDOVER_S = 600      # a gap longer than this is not a handover, it is an outage


def previous_run_end():
    """When the last run stopped, or None if this is the first ever."""
    if not RUNS.exists():
        return None
    lines = RUNS.read_text(encoding="utf-8").strip().splitlines()
    return json.loads(lines[-1])["end"] if lines else None


def main(minutes=0.0):
    run_id = uuid.uuid4().hex[:12]
    started = int(time.time())
    log = EventLog()

    cold = not STATE.exists()
    open_now = load_state()
    prev_end = previous_run_end()
    gap = None if prev_end is None else started - prev_end
    # A cold start sees outages that may have been running for days. A long gap
    # sees ones that may have started at any point inside it. Either way the
    # start we record is a lower bound, and saying so costs one field.
    starts_uncertain = cold or gap is None or gap > HANDOVER_S

    events_at_start = count_events_on_disk()
    n_st, changed = refresh_stations()
    print("run {}: {} stations{}, {} outages carried over, gap {}".format(
        run_id, n_st, " (metadata changed)" if changed else "", len(open_now),
        "cold start" if cold else "{}s".format(gap)), flush=True)
    if starts_uncertain:
        print("  starts on the first file are recorded as lower bounds", flush=True)

    etag = None
    prev_updated = None
    first_file = True
    files = reqs = nomod = errs = skips = 0
    opened = closed = gapclosed = 0
    deadline = started + minutes * 60 if minutes else None

    try:
        while deadline is None or time.time() < deadline:
            tick = time.time()
            try:
                payload, etag = fetch(STATUS, etag)
                reqs += 1
            except Exception as exc:
                errs += 1
                print("  error: {!r}".format(exc), flush=True)
            else:
                if payload is None:
                    nomod += 1
                else:
                    files += 1
                    upd = payload.get("last_updated")
                    # The 60s poll is only safe while publication stays slower
                    # than 60s. A jump here means a file was skipped, and that
                    # must surface as a number rather than as missing outages.
                    if prev_updated and upd and upd - prev_updated > SKIP_GAP_S:
                        skips += 1
                        print("  WARNING: {}s between published files".format(
                            upd - prev_updated), flush=True)
                    prev_updated = upd

                    o, c, g = step(payload, log, open_now, run_id, first_file,
                                   starts_uncertain)
                    opened += o
                    closed += c
                    gapclosed += g
                    if o or c:
                        log.flush()
                        save_state(open_now)
                        write_heartbeat(run_id, events_at_start + log.n, log.n, started)
                    first_file = False
                    if files % 15 == 0:
                        print("  {} files  open:{}  +{} -{}".format(
                            files, len(open_now), opened, closed), flush=True)

            time.sleep(max(0.0, POLL_S - (time.time() - tick)))
    except KeyboardInterrupt:
        print("stopped by hand", flush=True)

    log.flush()
    log.close()
    save_state(open_now)
    write_heartbeat(run_id, events_at_start + log.n, log.n, started)

    ended = int(time.time())
    RUNS.parent.mkdir(parents=True, exist_ok=True)
    with RUNS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "run": run_id, "start": started, "end": ended,
            "files": files, "requests": reqs, "not_modified": nomod,
            "errors": errs, "suspected_skips": skips,
            "opened": opened, "closed": closed, "closed_in_gap": gapclosed,
            "still_open": len(open_now), "events": log.n,
            "events_at_start": events_at_start,
            "gap_s": gap, "cold_start": int(cold),
            "starts_uncertain": int(starts_uncertain),
        }, separators=(",", ":")) + "\n")

    print("run {} ended after {:.0f} min: {} files, {} opened, {} closed "
          "({} during the gap), {} errors, {} skips".format(
              run_id, (ended - started) / 60, files, opened, closed,
              gapclosed, errs, skips), flush=True)


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 0.0)
