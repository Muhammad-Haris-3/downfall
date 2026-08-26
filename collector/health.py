"""
Is the record healthy? Run on a schedule, and fail loudly when it is not.

This exists because two failures ran unnoticed for hours each:

  M1-T8b  the collector wrote five hours of events into an unlinked file while
          reporting success at every checkpoint
  M1-T8c  fifteen git conflict markers made 42,000 events unparseable, and the
          collector went on committing happily on top of them

Neither was subtle once looked at. Nothing was looking. Every check here would
have caught one of them within a day, and the point is not the individual
checks - it is that something runs them without being asked.

A check FAILS when the record is damaged or collection has stopped. It WARNS
when a number is worse than it should be but the record is still sound. Warnings
do not fail the job, because a check that cries wolf gets muted and then the
next real failure is invisible too.

Usage:  python collector/health.py
Exit:   0 healthy (warnings allowed), 1 unhealthy
"""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.events import coverage, load_outages  # noqa: E402

EVENTS = ROOT / "data" / "events"

# A run is up to 350 minutes and checkpoints every 30, so a log with nothing new
# for two hours means collection has stopped, not that it is between commits.
STALE_HOURS = 2.0
MIN_RECENT_COVERAGE = 0.90     # warn below; steady state is ~99.9%
MAX_LOST_CLOSE_RATE = 0.05     # warn above; currently ~2.9%

fails, warns = [], []


def check(ok, message, fatal=True):
    if ok:
        print("  ok    {}".format(message))
    elif fatal:
        fails.append(message)
        print("  FAIL  {}".format(message))
    else:
        warns.append(message)
        print("  warn  {}".format(message))


def main():
    now = time.time()
    print("Downfall health check")

    # 1. The log parses at all. load_outages raises on a conflict marker and on
    #    malformed JSON, so this one check covers both corruptions seen so far.
    print("\nlog integrity")
    stats = {}
    try:
        outages = load_outages(stats=stats)
        check(True, "log parses: {:,} outages".format(len(outages)))
    except Exception as exc:
        check(False, "log does not parse: {}".format(exc))
        print("\nUNHEALTHY: the record is damaged. Nothing else was checked.")
        return 1

    # 2. Every file ends on a line boundary.
    torn = []
    for p in sorted(EVENTS.glob("*.ndjson")):
        if p.stat().st_size and p.open("rb").read()[-1:] != b"\n":
            torn.append(p.name)
    check(not torn, "no torn lines" if not torn else "torn: {}".format(torn))

    # 3. Collection is still running.
    print("\ncollection")
    newest = max((p.stat().st_mtime for p in EVENTS.glob("*.ndjson")), default=0)
    covered, span, runs = coverage()
    last_end = max((r["end"] for r in runs), default=0)
    age_h = (now - max(newest, last_end)) / 3600
    check(age_h < STALE_HOURS,
          "last activity {:.1f} h ago (stale above {:.0f} h)".format(age_h, STALE_HOURS))

    # 4. Coverage over the last day, which is the figure that says whether the
    #    chain is holding now rather than how the first day went.
    day = now - 86400
    recent = [r for r in runs if r["end"] > day]
    cov = sum(min(r["end"], now) - max(r["start"], day) for r in recent)
    base = now - max(day, min((r["start"] for r in runs), default=now))
    frac = cov / base if base > 0 else 0.0
    check(frac >= MIN_RECENT_COVERAGE,
          "coverage last 24h {:.1%}".format(frac), fatal=False)

    # 5. Every run that wrote events also recorded what it observed.
    #
    # A run records its coverage when it ends. One died without doing so and six
    # hours of collection became invisible - the log had the events, the
    # coverage record had nothing, and the only symptom was a coverage figure
    # that looked bad for no stated reason. This names the cause directly.
    from analysis.events import HEARTBEAT, iter_events  # noqa: E402

    recorded = {r["run"] for r in runs}
    live = None
    if HEARTBEAT.exists():
        try:
            live = json.loads(HEARTBEAT.read_text()).get("run")
        except (OSError, ValueError):
            live = None
    # Three runs from before the recovery existed can never be recovered: their
    # heartbeats were overwritten before anything read them. Excluded by name
    # rather than left to warn forever - a warning that cannot ever clear is how
    # a reader learns to skip the warnings, and then the next real one is
    # invisible too. The fact stays recorded in the file itself.
    known = set()
    orphan_file = ROOT / "data" / "state" / "orphan_runs.json"
    if orphan_file.exists():
        known = {r["run"] for r in json.loads(orphan_file.read_text())["runs"]}

    wrote_events = {e.get("run") for e in iter_events()} - {None, "reconcile-m1-t8b"}
    orphans = wrote_events - recorded - {live} - known
    check(not orphans,
          "every run that wrote events recorded its coverage"
          if not orphans else
          "{} NEW run(s) wrote events but no coverage row: {}".format(
              len(orphans), ", ".join(sorted(orphans))),
          fatal=False)
    if known & wrote_events:
        print("  info  {} run(s) permanently uncountable, see "
              "data/state/orphan_runs.json".format(len(known & wrote_events)))

    # 6. Outages whose close never arrived. Excluded from every duration figure,
    #    so a rise costs completeness rather than correctness - a warning.
    print("\nrecord quality")
    lost = stats.get("lost_closes", 0)
    rate = lost / len(outages) if outages else 0.0
    check(rate <= MAX_LOST_CLOSE_RATE,
          "lost closes {:,} of {:,} ({:.1%})".format(lost, len(outages), rate),
          fatal=False)

    usable = sum(1 for o in outages if o.usable_duration is not None)
    print("  info  {:,} outages carry a usable duration".format(usable))
    print("  info  {:.1f} h observed over a {:.1f} h span, {} runs".format(
        covered / 3600, span / 3600, len(runs)))

    print("\n{}: {} failure(s), {} warning(s)".format(
        "UNHEALTHY" if fails else "healthy", len(fails), len(warns)))
    for m in fails:
        print("  FAIL  {}".format(m))
    for m in warns:
        print("  warn  {}".format(m))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
