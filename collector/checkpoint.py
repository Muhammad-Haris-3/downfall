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


def main():
    whole, torn = files_are_whole()
    if not whole:
        print("torn line in {} - skipping this checkpoint".format(", ".join(torn)),
              file=sys.stderr)
        return 1

    events, opens, closes, still_open = tally()
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
