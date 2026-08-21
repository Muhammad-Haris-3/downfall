"""
One-off repair after the event loss of FINDINGS M1-T8b.

When the collector's writes stopped reaching the log, the state file went on
being updated - it is written atomically and so opens by name every time. The
result is a state file holding outages whose `open` events are not in the log
at all, and a log holding `open` events for outages the state has since closed.

Restarting cold on top of that would leave the log permanently inconsistent in
two ways: opens with no close, and closes with no open. `load_outages` raises on
the first and silently drops the second, and silently dropping is the worse of
the two.

So before restarting, every outage the state still holds is closed explicitly,
flagged `u` - ended at a time we did not observe. That is exactly what happened:
they did end, or they did not, and either way we stopped being able to see. The
flag means none of them contributes a duration to anything.

This is a repair, not a routine. It runs once, and the log records that it ran.

Usage:  python collector/reconcile.py [--dry-run]
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from collector.collect import (EVENTS, HEARTBEAT, STATE, EventLog,  # noqa: E402
                               count_events_on_disk)


def main():
    dry = "--dry-run" in sys.argv

    # Derived from the LOG, not from the state file.
    #
    # The first attempt closed what the state still held, and the log stayed
    # inconsistent - because the loss ran in both directions. The state kept
    # updating while the log did not, so the log also holds `open` events whose
    # matching `close` never reached it. Those are invisible to the state, which
    # has long since forgotten them.
    #
    # The log is the record being repaired, so the log is what has to be read.
    unmatched = {}
    for p in sorted(EVENTS.glob("*.ndjson")):
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                ev = json.loads(line)
                key = "{}|{}".format(ev["st"], ev["k"])
                if ev["ev"] == "open":
                    unmatched[key] = ev
                else:
                    unmatched.pop(key, None)

    before = count_events_on_disk()
    print("{} opens with no close in the log, {} events total".format(
        len(unmatched), before))
    if not unmatched:
        print("log is already consistent")
        if STATE.exists():
            STATE.write_text("{}")
        return 0

    if dry:
        for k in list(unmatched)[:5]:
            print("  would close {}".format(k))
        print("  ... and {} more".format(max(0, len(unmatched) - 5)))
        return 0

    now = int(time.time())
    log = EventLog()
    for key in sorted(unmatched):
        station, kind = key.split("|", 1)
        # `u` marks an end we did not observe. The timestamp is when we gave up
        # watching, not when the station recovered - which is the whole reason
        # the flag exists and the reason no duration may be built from it.
        log.append({"ev": "close", "st": station, "k": kind, "ts": now,
                    "run": "reconcile-m1-t8b", "u": 1})
    log.flush()
    log.close()

    STATE.write_text("{}")
    if HEARTBEAT.exists():
        HEARTBEAT.unlink()

    after = count_events_on_disk()
    print("closed {} outages, all flagged as having an unobserved end".format(
        len(unmatched)))
    print("log {} -> {} events; state cleared for a cold restart".format(
        before, after))
    return 0


if __name__ == "__main__":
    sys.exit(main())
