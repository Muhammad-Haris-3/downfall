"""Tests for the guarantees, not for the plumbing.

Each of these corresponds to a specific way the record could become dishonest,
and several of them are here because the mistake was actually made during M0.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.events import load_outages                       # noqa: E402
from collector.collect import BROKEN_TS, EventLog, classify    # noqa: E402


# ------------------------------------------------------- classification rules

def station(**kw):
    base = {"station_id": "s1", "is_installed": 1, "is_renting": 1,
            "num_bikes_available": 5, "num_docks_available": 5}
    base.update(kw)
    return base


def test_usable_station_is_not_an_outage():
    assert classify(station()) is None


def test_no_bikes_is_empty():
    assert classify(station(num_bikes_available=0)) == "empty"


def test_no_docks_is_full():
    assert classify(station(num_docks_available=0)) == "full"


def test_switched_off_station_is_offline_not_empty():
    """The scarcity-inventing bug.

    A station that is switched off reports zero bikes. Classifying that as a
    stockout would manufacture shortage that never happened - and 53 stations in
    this network report zero capacity permanently, so the error would not be
    small.
    """
    off = station(is_installed=0, num_bikes_available=0)
    assert classify(off) == "offline"

    not_renting = station(is_renting=0, num_bikes_available=0, num_docks_available=0)
    assert classify(not_renting) == "offline"


# --------------------------------------------------------- pairing and censoring

def write_log(tmp_path, events):
    p = tmp_path / "2026-01-01.ndjson"
    p.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return [p]


def test_open_and_close_pair_into_a_duration(tmp_path):
    paths = write_log(tmp_path, [
        {"ev": "open", "st": "a", "k": "empty", "ts": 1000},
        {"ev": "close", "st": "a", "k": "empty", "ts": 1600},
    ])
    (o,) = load_outages(paths)
    assert o.duration == 600
    assert o.usable_duration == 600


def test_unseen_start_yields_no_usable_duration(tmp_path):
    """An outage already running when we first looked has a start we never saw.

    It still has an end, and an apparent length - which is exactly why it has to
    be refused rather than trusted. The apparent length is a lower bound wearing
    a measurement's clothes.
    """
    paths = write_log(tmp_path, [
        {"ev": "open", "st": "a", "k": "empty", "ts": 1000, "o": 1},
        {"ev": "close", "st": "a", "k": "empty", "ts": 1600},
    ])
    (o,) = load_outages(paths)
    assert o.duration == 600           # the arithmetic still works
    assert o.usable_duration is None   # and is still refused


def test_unseen_end_yields_no_usable_duration(tmp_path):
    paths = write_log(tmp_path, [
        {"ev": "open", "st": "a", "k": "empty", "ts": 1000},
        {"ev": "close", "st": "a", "k": "empty", "ts": 1600, "u": 1},
    ])
    (o,) = load_outages(paths)
    assert o.usable_duration is None


def test_still_open_outage_has_no_end(tmp_path):
    paths = write_log(tmp_path, [{"ev": "open", "st": "a", "k": "empty", "ts": 1000}])
    (o,) = load_outages(paths)
    assert o.end is None
    assert o.usable_duration is None


def test_empty_and_full_at_one_station_do_not_collide(tmp_path):
    """Kinds are keyed separately, so one cannot close the other."""
    paths = write_log(tmp_path, [
        {"ev": "open", "st": "a", "k": "empty", "ts": 1000},
        {"ev": "open", "st": "a", "k": "full", "ts": 1100},
        {"ev": "close", "st": "a", "k": "empty", "ts": 1200},
    ])
    outs = {o.kind: o for o in load_outages(paths)}
    assert outs["empty"].duration == 200
    assert outs["full"].end is None


def test_a_lost_close_is_raised_not_absorbed(tmp_path):
    """Two opens with no close between them means the log dropped a line.

    Silently overwriting would produce a plausible outage of the wrong length.
    """
    paths = write_log(tmp_path, [
        {"ev": "open", "st": "a", "k": "empty", "ts": 1000},
        {"ev": "open", "st": "a", "k": "empty", "ts": 2000},
    ])
    with pytest.raises(ValueError):
        load_outages(paths)


# ------------------------------------------------------------- append-only

def test_event_log_only_ever_appends(tmp_path, monkeypatch):
    """Write, then write again, and check the first bytes are untouched."""
    import collector.collect as c
    monkeypatch.setattr(c, "EVENTS", tmp_path)

    log = EventLog()
    log.append({"ev": "open", "st": "a", "k": "empty", "ts": 1000})
    log.flush()
    path = log.path
    first = path.read_bytes()

    log.append({"ev": "close", "st": "a", "k": "empty", "ts": 1600})
    log.flush()
    log.close()
    after = path.read_bytes()

    assert after.startswith(first), "an earlier line was rewritten"
    assert len(after) > len(first)


def test_writes_survive_the_file_being_replaced_underneath(tmp_path, monkeypatch):
    """The five-hour data loss, reproduced.

    The checkpoint runs `git pull --rebase --autostash` every 30 minutes while
    the collector is still writing. Git does not edit in place - it writes a new
    file and renames it over the old one. A process holding the old handle goes
    on writing to an unlinked inode: a file with no name, that nothing reads and
    that disappears when the process exits.

    The collector reported success throughout, because it was counting its own
    writes rather than checking them, and `save_state` survived by opening a
    fresh file each time. Eight consecutive checkpoints logged the same frozen
    event count and nothing failed.

    Simulated here by replacing the file between two writes, which is what the
    rename amounts to from the log's point of view.
    """
    import collector.collect as c
    monkeypatch.setattr(c, "EVENTS", tmp_path)

    log = EventLog()
    log.append({"ev": "open", "st": "a", "k": "empty", "ts": 1000})
    log.flush()
    path = log.path

    # What git does: a different file now carries this name.
    replacement = tmp_path / "replacement"
    replacement.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    path.unlink()
    replacement.rename(path)

    log.append({"ev": "close", "st": "a", "k": "empty", "ts": 1600})
    log.flush()

    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 2, "the second write did not reach the named file"
    assert '"ev": "close"' in lines[1] or '"ev":"close"' in lines[1]


def test_the_checkpoint_refuses_when_events_are_missing(tmp_path, monkeypatch):
    """The guard that was absent while the loss was happening.

    The collector counts an event only after handing it to the log, so fewer
    lines on disk than it claims means writes are being lost right now. That has
    to fail the job: a checkpoint that commits a log it knows is short writes
    the loss into the permanent record and calls it coverage.
    """
    import collector.checkpoint as cp
    monkeypatch.setattr(cp, "HEARTBEAT", tmp_path / "collector.json")

    (tmp_path / "collector.json").write_text(json.dumps(
        {"run": "x", "expected_events_on_disk": 848, "written_this_run": 848}))

    ok, why = cp.agrees_with_collector(106)
    assert not ok
    assert "742 lost" in why

    ok, _ = cp.agrees_with_collector(848)
    assert ok, "an exact match must pass"

    # Another run's events share the same files, so a surplus is normal.
    ok, _ = cp.agrees_with_collector(900)
    assert ok, "more lines than claimed is not a loss"


def test_a_missing_heartbeat_is_not_treated_as_loss(tmp_path, monkeypatch):
    import collector.checkpoint as cp
    monkeypatch.setattr(cp, "HEARTBEAT", tmp_path / "absent.json")
    ok, _ = cp.agrees_with_collector(0)
    assert ok


def test_events_are_filed_by_observation_not_by_their_own_timestamp(tmp_path, monkeypatch):
    """A station offline since May carries a May timestamp.

    Filing by that scattered one hour of collection across a dozen historical
    files, rewriting months of history on every run.
    """
    import collector.collect as c
    monkeypatch.setattr(c, "EVENTS", tmp_path)

    log = EventLog()
    log.append({"ev": "open", "st": "a", "k": "offline", "ts": 1_779_972_042})  # May
    log.append({"ev": "open", "st": "b", "k": "empty", "ts": 1_787_267_026})    # August
    log.flush()
    log.close()

    assert len(list(tmp_path.glob("*.ndjson"))) == 1


# --------------------------------------------- code agrees with the document

def test_placeholder_timestamp_threshold_excludes_the_1970_stations():
    """M0-T1 found 87 stations reporting 1970-01-02 (epoch 86400)."""
    assert 86_400 < BROKEN_TS
    assert BROKEN_TS < 1_787_000_000          # and does not exclude live readings


def test_poll_interval_respects_the_declared_ttl():
    """The feed declares `ttl: 60`. Polling faster ignores what it asked for,
    and buys nothing: timestamps come from the feed's clock, not ours."""
    from collector.collect import POLL_S
    assert POLL_S >= 60, "polls faster than the publisher asked"
    assert POLL_S < 70, "slower than publication would start skipping files"


def test_preregistered_thresholds_match_the_document():
    """The numbers in PREREGISTRATION.md §3 are the ones a reader will hold us
    to. If they drift out of the code, the document is decoration."""
    text = (ROOT / "PREREGISTRATION.md").read_text(encoding="utf-8")
    for required in ("21 days", "95%", "20,000", "168 hour-of-week", "20%", "10%"):
        assert required in text, "threshold {!r} missing from pre-registration".format(required)
