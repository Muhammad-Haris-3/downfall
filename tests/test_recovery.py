"""Tests for recovering a run that died without recording what it observed.

A run writes its coverage row when it ends, and only then - the rule that stops
a checkpoint counting the same time twice. The cost is that a killed run records
nothing, and one did: six hours of events in the log with no coverage for any of
it. These cover the salvage and, more importantly, its limits.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import collector.collect as c  # noqa: E402


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "HEARTBEAT", tmp_path / "collector.json")
    monkeypatch.setattr(c, "RUNS", tmp_path / "runs.ndjson")
    return tmp_path


def write_hb(env, run, started, at, written=100):
    (env / "collector.json").write_text(json.dumps(
        {"run": run, "started": started, "at": at,
         "written_this_run": written, "expected_events_on_disk": written}))


def write_runs(env, runs):
    (env / "runs.ndjson").write_text(
        "".join(json.dumps(r) + "\n" for r in runs), encoding="utf-8")


def test_an_abandoned_run_gets_its_coverage_back(env):
    write_runs(env, [{"run": "older", "start": 1000, "end": 2000}])
    write_hb(env, "died", started=2000, at=5000)

    row = c.recover_abandoned_run()
    assert row is not None
    assert row["start"] == 2000
    assert row["end"] == 5000
    assert row["recovered"] == 1

    lines = (env / "runs.ndjson").read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[-1])["run"] == "died"


def test_coverage_stops_at_the_last_heartbeat_not_at_now(env):
    """The bound that makes the salvage honest.

    A run that stopped writing stops accruing coverage at the point it stopped.
    Crediting it to the present would hand a dead collector full marks for the
    hours it was dead, which is the opposite of what the coverage floor is for.
    """
    write_runs(env, [{"run": "older", "start": 0, "end": 100}])
    write_hb(env, "died", started=1000, at=1600)
    row = c.recover_abandoned_run()
    assert row["end"] == 1600, "credited beyond the last heartbeat"


def test_a_run_that_recorded_itself_is_not_recovered_twice(env):
    """Double-counting coverage is the failure the write-on-end rule prevents;
    the recovery must not reintroduce it."""
    write_runs(env, [{"run": "fine", "start": 1000, "end": 2000}])
    write_hb(env, "fine", started=1000, at=2000)
    assert c.recover_abandoned_run() is None
    assert len((env / "runs.ndjson").read_text().strip().splitlines()) == 1


def test_a_heartbeat_without_a_start_recovers_nothing(env):
    """Heartbeats written before `started` existed cannot bound a span, and a
    guessed start would be an invented measurement."""
    write_runs(env, [{"run": "older", "start": 0, "end": 100}])
    (env / "collector.json").write_text(json.dumps(
        {"run": "old-format", "at": 5000, "written_this_run": 10}))
    assert c.recover_abandoned_run() is None


def test_no_heartbeat_at_all_recovers_nothing(env):
    write_runs(env, [{"run": "older", "start": 0, "end": 100}])
    assert c.recover_abandoned_run() is None


def test_the_recovered_row_is_marked_as_recovered(env):
    """It must never be mistaken for a row a run wrote about itself: its
    counters are unknown, and reporting them as zero would be a lie."""
    write_runs(env, [{"run": "older", "start": 0, "end": 100}])
    write_hb(env, "died", started=1000, at=1600)
    row = c.recover_abandoned_run()
    assert row["recovered"] == 1
    assert row["files"] is None
    assert row["opened"] is None
