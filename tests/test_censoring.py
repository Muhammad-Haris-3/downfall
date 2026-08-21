"""Tests for the censoring join.

Every case here is one someone could work out with a pen, which is the point:
the join is where an arithmetic slip would be invisible, because the output is
plausible for almost any bug.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.censoring import censored_minutes, coverage_by_hour, split_by_hour  # noqa: E402
from analysis.events import Outage                                                # noqa: E402

H = 3600
T0 = 1_787_000_000 - (1_787_000_000 % H)      # an exact hour boundary


def out(kind="empty", start=0, end=None, station="a", start_seen=True, end_seen=True):
    return Outage(station=station, kind=kind, start=T0 + start,
                  end=None if end is None else T0 + end,
                  start_seen=start_seen, end_seen=end_seen)


def runs(*spans):
    return [{"start": T0 + a, "end": T0 + b} for a, b in spans]


# --------------------------------------------------------------- interval split

def test_interval_inside_one_hour():
    assert list(split_by_hour(T0 + 600, T0 + 900)) == [(T0, 300)]


def test_interval_spanning_two_hours_splits_at_the_boundary():
    assert list(split_by_hour(T0 + 3000, T0 + 4200)) == [(T0, 600), (T0 + H, 600)]


def test_interval_spanning_three_hours_fills_the_middle():
    got = list(split_by_hour(T0 + 3000, T0 + 3 * H + 600))
    assert got == [(T0, 600), (T0 + H, H), (T0 + 2 * H, H), (T0 + 3 * H, 600)]


def test_zero_length_interval_yields_nothing():
    assert list(split_by_hour(T0, T0)) == []


# ------------------------------------------------------------------- coverage

def test_coverage_never_exceeds_an_hour_even_if_runs_overlap():
    cov = coverage_by_hour(runs((0, H), (0, H)))
    assert cov[T0] == H


# ------------------------------------------------------ the rules that matter

def test_empty_and_full_are_kept_apart():
    """They suppress different events. A station with no docks records
    departures perfectly well, and summing them would say otherwise."""
    rows, _ = censored_minutes([out("empty", 0, 600), out("full", 0, 1200)],
                               runs((0, H)))
    (r,) = rows
    assert r["empty_s"] == 600
    assert r["full_s"] == 1200


def test_offline_hour_leaves_the_denominator_entirely():
    """Not an hour of zero demand - an hour with no station.

    Counting it as a usable hour would dilute every rate computed over the
    network, and the dilution would grow with the number of broken stations.
    """
    rows, exc = censored_minutes([out("offline", 0, H)], runs((0, H)))
    assert rows == []
    assert exc["offline_outages"] == 1


def test_an_unobserved_boundary_contributes_no_minutes():
    """Its length is a lower bound, and a lower bound added to a total makes
    the total neither a bound nor a measurement."""
    rows, exc = censored_minutes([out("empty", 0, 600, start_seen=False)], runs((0, H)))
    assert rows == []
    assert exc["unobserved_boundary"] == 1

    rows, exc = censored_minutes([out("empty", 0, 600, end_seen=False)], runs((0, H)))
    assert rows == []
    assert exc["unobserved_boundary"] == 1


def test_a_still_open_outage_contributes_no_minutes():
    rows, exc = censored_minutes([out("empty", 0, None)], runs((0, H)))
    assert rows == []
    assert exc["still_open"] == 1


def test_fraction_is_of_the_observed_hour_not_the_nominal_hour():
    """We watched for 20 minutes and it was empty throughout.

    It was empty for all of what we saw. Reporting 33% would describe our
    collection schedule, not the station.
    """
    rows, _ = censored_minutes([out("empty", 0, 1200)], runs((0, 1200)),
                               min_coverage=0.0)
    (r,) = rows
    assert r["covered_s"] == 1200
    assert r["empty_frac"] == 1.0


def test_an_hour_we_barely_watched_is_dropped_not_scaled():
    rows, exc = censored_minutes([out("empty", 0, 300)], runs((0, 600)))
    assert rows == []
    assert exc["low_coverage_hours"] == 1


def test_outage_minutes_never_exceed_observed_minutes():
    """Clock skew between the feed's timestamps and our run windows could
    otherwise produce an hour more than 100% empty."""
    rows, _ = censored_minutes([out("empty", 0, H)], runs((0, 1800)),
                               min_coverage=0.0)
    (r,) = rows
    assert r["empty_s"] == 1800
    assert r["empty_frac"] == 1.0


def test_one_outage_across_two_hours_lands_in_both():
    rows, _ = censored_minutes([out("empty", 3000, 4200)], runs((0, 2 * H)))
    by_hour = {r["hour_utc"]: r for r in rows}
    assert by_hour[T0]["empty_s"] == 600
    assert by_hour[T0 + H]["empty_s"] == 600


def test_two_stations_do_not_pool():
    rows, _ = censored_minutes(
        [out("empty", 0, 600, station="a"), out("empty", 0, 1800, station="b")],
        runs((0, H)))
    by_station = {r["station"]: r for r in rows}
    assert by_station["a"]["empty_s"] == 600
    assert by_station["b"]["empty_s"] == 1800
