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


def iter_events(paths=None):
    for p in sorted(paths or EVENTS.glob("*.ndjson")):
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)


def load_outages(paths=None):
    """Pair the log into outages, in the order they were observed."""
    open_now = {}
    out = []
    for ev in iter_events(paths):
        key = (ev["st"], ev["k"])
        if ev["ev"] == "open":
            # A second open with no close between them would mean the log lost a
            # close. Surfaced rather than silently overwritten.
            if key in open_now:
                raise ValueError("open without close for {}".format(key))
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
    return out


def coverage():
    """(covered_seconds, span_seconds, runs) from the per-run record."""
    if not RUNS.exists():
        return 0, 0, []
    runs = [json.loads(l) for l in RUNS.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not runs:
        return 0, 0, []
    covered = sum(r["end"] - r["start"] for r in runs)
    span = max(r["end"] for r in runs) - min(r["start"] for r in runs)
    return covered, span, runs
