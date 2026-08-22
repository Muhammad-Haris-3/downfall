"""
Remove git conflict markers from the event log.

A one-off repair, like `reconcile.py`. It exists because a failed rebase left
`<<<<<<< HEAD`, `=======` and `>>>>>>> <sha>` in the log and the next checkpoint
committed them - fifteen lines that made 42,000 events unreadable.

WHAT THIS IS ALLOWED TO REMOVE, AND WHY THAT IS NOT A REWRITE
--------------------------------------------------------------
The log is append-only and nothing may edit a recorded event. Conflict markers
are not recorded events. They are git's annotation of its own failure, written
into the file by a tool, and they carry no observation. Removing them restores
the file to what the collector actually wrote.

The distinction matters enough to be enforced: this refuses to run if removing
the markers would change the number of parseable events, which is the signature
of an edit rather than a repair.

Usage:  python collector/strip_conflicts.py [--dry-run]
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVENTS = ROOT / "data" / "events"
MARKERS = ("<<<<<<<", "=======", ">>>>>>>")


def classify(path):
    """(kept lines, marker lines, parseable event count)."""
    kept, marks, parsed = [], [], 0
    with path.open("rb") as fh:
        for raw in fh:
            s = raw.decode("utf-8", "replace").strip()
            if not s:
                continue
            if s.startswith(MARKERS):
                marks.append(s[:70])
                continue
            kept.append(s)
            try:
                json.loads(s)
                parsed += 1
            except Exception:
                pass
    return kept, marks, parsed


def main():
    dry = "--dry-run" in sys.argv
    total_marks = 0
    total_events = 0

    for p in sorted(EVENTS.glob("*.ndjson")):
        kept, marks, parsed = classify(p)
        total_marks += len(marks)
        total_events += parsed
        if not marks:
            print("{:<24} clean, {:,} events".format(p.name, parsed))
            continue

        print("{:<24} {} marker lines, {:,} events survive".format(
            p.name, len(marks), parsed))
        for m in marks:
            print("      - {}".format(m))

        if parsed != len(kept):
            print("      REFUSED: {} kept lines but only {} parse. Removing "
                  "markers would not be the only change.".format(len(kept), parsed))
            return 1

        if not dry:
            tmp = p.with_suffix(".tmp")
            tmp.write_text("\n".join(kept) + "\n", encoding="utf-8", newline="\n")
            tmp.replace(p)

    print("\n{} marker lines {}; {:,} events".format(
        total_marks, "found" if dry else "removed", total_events))
    return 0


if __name__ == "__main__":
    sys.exit(main())
