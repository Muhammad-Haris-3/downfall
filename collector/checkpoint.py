"""
Make the collected record safe to commit while collection is still running.

The collector now runs for up to 350 minutes in one job. Committing only at the
end would mean a killed runner loses everything since the last handover, so the
workflow checkpoints periodically - which means git reads the event log while it
is being appended to.

Two things have to hold before that is safe:

  THE LAST LINE MUST BE COMPLETE. The collector writes and fsyncs whole lines,
  but a commit landing mid-write would capture half of one. A truncated JSON
  line in an append-only log is not recoverable by a later append: the next line
  starts on the same row and both are lost. So this waits for every event file
  to end in a newline, and refuses rather than committing a torn file.

  A CHECKPOINT IS NOT A RUN. `data/runs.ndjson` gets its row when the run ends,
  and only then. A checkpoint that wrote a partial run record would put coverage
  in the record twice, and coverage is the number the pre-registration gates on.

Exit codes: 0 safe to commit, 1 not safe (caller should skip this checkpoint and
try again at the next one - the data is not lost, only not yet committed).

Usage:  python collector/checkpoint.py [--message]
"""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVENTS = ROOT / "data" / "events"
STATE = ROOT / "data" / "state" / "open.json"
HEARTBEAT = ROOT / "data" / "state" / "collector.json"

RETRIES = 5
WAIT_S = 3


def files_are_whole():
    """Every event file ends on a line boundary."""
    for _ in range(RETRIES):
        torn = []
        for p in sorted(EVENTS.glob("*.ndjson")):
            if p.stat().st_size == 0:
                continue
            with p.open("rb") as fh:
                fh.seek(-1, 2)
                if fh.read(1) != b"\n":
                    torn.append(p.name)
        if not torn:
            return True, []
        time.sleep(WAIT_S)
    return False, torn


def tally():
    events = opens = closes = 0
    for p in sorted(EVENTS.glob("*.ndjson")):
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                events += 1
                if '"ev":"open"' in line:
                    opens += 1
                else:
                    closes += 1
    still_open = len(json.loads(STATE.read_text())) if STATE.exists() else 0
    return events, opens, closes, still_open


CONFLICT_MARKERS = ("<<<<<<<", "=======", ">>>>>>>")


def has_conflict_markers():
    """Any line git left behind after a failed merge.

    A rebase that hits a conflict leaves the markers in the working tree. The
    commit script used to swallow that failure with `|| true`, and the next
    checkpoint's `git add data/` staged the markers and committed them - fifteen
    lines that made 42,000 events unreadable (FINDINGS M1-T8c).

    Checked before anything is staged, because once committed the damage is in
    the permanent record of a log that is supposed to be append-only.
    """
    found = []
    for p in sorted(EVENTS.glob("*.ndjson")):
        with p.open(encoding="utf-8", errors="replace") as fh:
            for n, line in enumerate(fh, 1):
                if line.strip().startswith(CONFLICT_MARKERS):
                    found.append("{}:{}".format(p.name, n))
                    break
    return found


def agrees_with_collector(events_on_disk):
    """Does the log hold what the running collector says it wrote?

    This is the guard that was missing when a checkpoint reported "590 events"
    eight times in a row while five hours of collection went into an unlinked
    file (FINDINGS M1-T8b). Nothing failed, because nothing was checking.

    A shortfall is never acceptable: the collector counts an event only after
    handing it to the log, so fewer lines on disk than it claims means writes
    are being lost right now. More lines is fine - another run's events are in
    the same files.

    Returns (ok, message). A missing heartbeat is not a failure: an older
    collector, or one that has not yet written anything, has nothing to claim.
    """
    if not HEARTBEAT.exists():
        return True, "no heartbeat; nothing claimed"
    hb = json.loads(HEARTBEAT.read_text())
    expected = hb.get("expected_events_on_disk")
    if expected is None:
        return True, "heartbeat carries no expectation"
    if events_on_disk < expected:
        return False, ("collector wrote {} events but only {} are on disk - "
                       "{} lost".format(expected, events_on_disk,
                                        expected - events_on_disk))
    return True, "{} on disk, {} expected".format(events_on_disk, expected)


def main():
    conflicts = has_conflict_markers()
    if conflicts:
        print("CONFLICT MARKERS in {} - refusing to commit a damaged log"
              .format(", ".join(conflicts)), file=sys.stderr)
        return 2

    whole, torn = files_are_whole()
    if not whole:
        print("torn line in {} - skipping this checkpoint".format(", ".join(torn)),
              file=sys.stderr)
        return 1

    events, opens, closes, still_open = tally()

    ok, why = agrees_with_collector(events)
    if not ok:
        # Loud, and fatal. A checkpoint that commits a log it knows is short
        # would write the loss into the permanent record and call it coverage.
        print("EVENT LOSS DETECTED: {}".format(why), file=sys.stderr)
        return 2
    if "--message" in sys.argv:
        print("Checkpoint: {} events, {} open / {} closed, {} still out".format(
            events, opens, closes, still_open))
        print()
        print("Mid-run checkpoint. The run's own coverage row is written to "
              "data/runs.ndjson when the run ends, never here - counting it "
              "twice would inflate the number the pre-registration gates on.")
    else:
        print("safe: {} events, {} still open".format(events, still_open))
    return 0


if __name__ == "__main__":
    sys.exit(main())
