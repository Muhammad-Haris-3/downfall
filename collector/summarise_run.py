"""Print a commit subject and body describing the most recent collection run.

Kept as a file rather than a heredoc inside the workflow so that it can be run
and tested like any other code. The commit history doubles as the coverage log,
so what this prints is the part of the record most people will actually read.
"""

import json
import sys
from pathlib import Path

RUNS = Path(__file__).resolve().parent.parent / "data" / "runs.ndjson"


def main():
    lines = RUNS.read_text(encoding="utf-8").strip().splitlines()
    if not lines:
        print("Collect: no run recorded")
        return 0
    r = json.loads(lines[-1])

    print("Collect: {} files, +{} -{} outages, {} still open".format(
        r["files"], r["opened"], r["closed"], r["still_open"]))
    print()
    print("run {} covered {} min: {} requests, {} already held".format(
        r["run"], round((r["end"] - r["start"]) / 60), r["requests"],
        r["not_modified"]))

    # Only mention the failure counters when they are non-zero. A commit subject
    # that says "0 errors" every hour trains the reader to stop looking.
    flags = []
    if r["errors"]:
        flags.append("{} failed requests".format(r["errors"]))
    if r["suspected_skips"]:
        flags.append("{} suspected skipped files".format(r["suspected_skips"]))
    if r["closed_in_gap"]:
        flags.append("{} outages ended during the handover and carry no duration"
                     .format(r["closed_in_gap"]))
    if flags:
        print()
        print("; ".join(flags))
    return 0


if __name__ == "__main__":
    sys.exit(main())
