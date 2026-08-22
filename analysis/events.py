"""Read the append-only event log back into outages.

An outage is an `open` event and the `close` that follows it for the same
station and kind. This module is the only place that pairing happens, so every
analysis inherits the same rules about what is usable:

  o=1   start not observed - the outage was already running when we first looked
  u=1   end not observed - it finished during a gap between runs

Neither is dropped. Both are returned with the flag intact, and it is the
caller's job to say out loud which it excluded.
"""

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVENTS = ROOT / "data" / "events"
RUNS = ROOT / "data" / "runs.ndjson"


@dataclass
class Outage:
    station: str
    kind: str
    start: int
    end: int | None          # None = still open at the end of the log
    start_seen: bool
    end_seen: bool

    @property
    def duration(self):
        return None if self.end is None else max(self.end - self.start, 0)

    @property
    def usable_duration(self):
        """A duration only counts when both of its ends were actually seen."""
        return self.duration if (self.start_seen and self.end_seen) else None


CONFLICT_MARKERS = ("<<<<<<<", "=======", ">>>>>>>")


def iter_events(paths=None):
    """Every event in the log, in the order it was written.

    NOT sorted by timestamp, and that was tried and reverted.

    An `open` carries the station's own `last_reported`; a `close` carries the
    newest `last_reported` anywhere in the network, because the recovering
    station is no longer in the outage set when the close is written. Those are
    two different clocks. A station whose own clock lags the network then
    produces an open whose timestamp precedes the close that came before it -
    202 events in the log do exactly this - and sorting by timestamp reorders
    them into an impossible sequence. Measured: file order gives 620 apparent
    lost closes, timestamp order gives 806. The 186 difference was manufactured
    by the sort.

    File order is correct because each run appends contiguously and runs do not
    overlap. `merge=union` (see .gitattributes) preserves each side's block, so
    a merged file is still a concatenation of ordered runs.

    A conflict marker raises rather than being skipped. They were committed into
    the log once (FINDINGS M1-T8c) and silently ignoring them would mean an
    analysis running happily over a file that is known to be damaged.
    """
    rows = []
    for p in sorted(paths or EVENTS.glob("*.ndjson")):
        with p.open(encoding="utf-8") as fh:
            for n, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                if line.startswith(CONFLICT_MARKERS):
                    raise ValueError(
                        "conflict marker at {}:{} - the log is damaged and must "
                        "be repaired, not read".format(p.name, n))
                rows.append(json.loads(line))
    return rows


def load_outages(paths=None, stats=None):
    """Pair the log into outages, in the order they were observed.

    `stats`, if given, is filled with counts the caller is expected to publish -
    at present `lost_closes`, the number of outages whose `close` never reached
    the log.
    """
    open_now = {}
    out = []
    lost_closes = 0
    for ev in iter_events(paths):
        key = (ev["st"], ev["k"])
        if ev["ev"] == "open":
            # A second open with no close between them means the log lost a
            # close - it happened once, when writes were going to an unlinked
            # file (FINDINGS M1-T8b).
            #
            # This used to raise. Raising was the wrong response: two damaged
            # events made the entire log unreadable, and the information the
            # duplicate carries is not nonsense. It says the previous outage
            # ended at a moment we did not see, which is a thing this schema
            # already knows how to express.
            #
            # So the previous outage is closed with its end unobserved - which
            # refuses it a duration, exactly as it should - and the count is
            # reported rather than absorbed.
            if key in open_now:
                prev = open_now[key]
                lost_closes += 1
                out.append(Outage(station=key[0], kind=key[1], start=prev["ts"],
                                  end=ev["ts"], start_seen=not prev.get("o"),
                                  end_seen=False))
            open_now[key] = ev
        else:
            o = open_now.pop(key, None)
            if o is None:
                # A close with no open belongs to a run whose file we do not
                # hold - possible when reading a subset of days.
                continue
            out.append(Outage(station=ev["st"], kind=ev["k"], start=o["ts"],
                              end=ev["ts"], start_seen=not o.get("o"),
                              end_seen=not ev.get("u")))
    for key, o in open_now.items():
        out.append(Outage(station=key[0], kind=key[1], start=o["ts"], end=None,
                          start_seen=not o.get("o"), end_seen=False))
    if stats is not None:
        stats["lost_closes"] = lost_closes
        stats["outages"] = len(out)
    return out


HEARTBEAT = ROOT / "data" / "state" / "collector.json"


def coverage():
    """(covered_seconds, span_seconds, runs) including the run happening now.

    A run writes its coverage row when it ends, and only then - counting it
    twice was the reason for that rule. But a run lasts up to 350 minutes, so
    for most of any given moment the newest run has recorded nothing, and
    coverage computed from completed rows alone understates by up to one run
    length. Measured on 2026-08-22: 81.9% against a true 99.9%, because the
    four hours then in progress were invisible.

    The heartbeat says which run is live and when it last wrote. If that run has
    no row yet, it is credited from its start to its last heartbeat - never
    beyond, so an abandoned run stops accruing coverage the moment it stops
    writing.
    """
    if not RUNS.exists():
        return 0, 0, []
    runs = [json.loads(l) for l in RUNS.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    if not runs:
        return 0, 0, []

    recorded = {r["run"] for r in runs}
    live = None
    if HEARTBEAT.exists():
        try:
            hb = json.loads(HEARTBEAT.read_text())
            if hb.get("run") not in recorded and hb.get("started") and hb.get("at"):
                live = {"run": hb["run"], "start": hb["started"], "end": hb["at"],
                        "in_progress": True}
        except (OSError, ValueError):
            live = None

    all_runs = runs + ([live] if live else [])
    covered = sum(r["end"] - r["start"] for r in all_runs)
    span = max(r["end"] for r in all_runs) - min(r["start"] for r in all_runs)
    return covered, span, all_runs
