"""Tests for the mid-run checkpoint.

The checkpoint's whole job is to refuse in one specific situation. A test suite
that only checked the happy path would leave the refusal untested, which is the
half that matters.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import collector.checkpoint as cp  # noqa: E402


@pytest.fixture
def events(tmp_path, monkeypatch):
    d = tmp_path / "events"
    d.mkdir()
    monkeypatch.setattr(cp, "EVENTS", d)
    monkeypatch.setattr(cp, "STATE", tmp_path / "open.json")
    # HEARTBEAT must be redirected too, or these tests read the repository's own
    # heartbeat. That file is absent on a development machine and present in CI,
    # so leaving it unpatched made the suite pass locally and fail on push -
    # the test was reporting on the machine it ran on, not on the code.
    monkeypatch.setattr(cp, "HEARTBEAT", tmp_path / "collector.json")
    monkeypatch.setattr(cp, "RETRIES", 2)
    monkeypatch.setattr(cp, "WAIT_S", 0)
    return d


def test_a_complete_file_is_safe_to_commit(events):
    (events / "2026-08-21.ndjson").write_text(
        '{"ev":"open","st":"a","k":"empty","ts":1}\n', encoding="utf-8")
    whole, torn = cp.files_are_whole()
    assert whole
    assert torn == []


def test_a_torn_last_line_is_refused(events):
    """The failure this exists for.

    A half-written line cannot be repaired by a later append: the collector's
    next write lands on the same row, and both records are lost. Committing it
    would put that corruption into the permanent history.
    """
    (events / "2026-08-21.ndjson").write_text(
        '{"ev":"open","st":"a","k":"empty","ts":1}\n{"ev":"open","st":"b"',
        encoding="utf-8")
    whole, torn = cp.files_are_whole()
    assert not whole
    assert "2026-08-21.ndjson" in torn


def test_one_torn_file_among_several_still_refuses(events):
    (events / "2026-08-20.ndjson").write_text('{"ev":"open"}\n', encoding="utf-8")
    (events / "2026-08-21.ndjson").write_text('{"ev":"open"', encoding="utf-8")
    whole, torn = cp.files_are_whole()
    assert not whole


def test_an_empty_file_is_not_torn(events):
    """A file the collector has opened but not yet written to is fine."""
    (events / "2026-08-21.ndjson").write_text("", encoding="utf-8")
    whole, _ = cp.files_are_whole()
    assert whole


def test_no_files_at_all_is_safe(events):
    whole, _ = cp.files_are_whole()
    assert whole


def test_tally_counts_opens_and_closes_separately(events):
    (events / "2026-08-21.ndjson").write_text(
        '{"ev":"open","st":"a","k":"empty","ts":1}\n'
        '{"ev":"open","st":"b","k":"full","ts":2}\n'
        '{"ev":"close","st":"a","k":"empty","ts":3}\n', encoding="utf-8")
    events_n, opens, closes, still_open = cp.tally()
    assert (events_n, opens, closes) == (3, 2, 1)


def test_checkpoint_never_writes_a_coverage_row(events, monkeypatch, capsys):
    """Coverage is the number PREREGISTRATION.md §3 gates on.

    A checkpoint that appended its own partial run record would count the same
    observed time twice, and the floor would be reached early on arithmetic
    rather than on collection.
    """
    (events / "2026-08-21.ndjson").write_text('{"ev":"open"}\n', encoding="utf-8")
    runs = events.parent / "runs.ndjson"
    monkeypatch.setattr(sys, "argv", ["checkpoint.py", "--message"])
    cp.main()
    assert not runs.exists(), "the checkpoint wrote a run record"
    assert "never here" in capsys.readouterr().out
