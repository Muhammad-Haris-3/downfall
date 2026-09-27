"""The §4 run: the pieces that decide which trips are hidden and how it is scored."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis.validation import (JUDGED, MAX_ABS_ERR, MAX_SIGNED_ERR,  # noqa: E402
                                 MIN_COHORT, impose, merge, passes, station_error)

ROOT = Path(__file__).resolve().parent.parent


def test_trips_inside_a_borrowed_outage_are_hidden_and_no_others():
    iv = merge([(100, 200), (300, 400)])
    t = np.array([99, 100, 150, 199, 200, 250, 300, 399, 400])
    assert impose(t, iv).tolist() == [False, True, True, True, False,
                                      False, True, True, False]


def test_overlapping_outages_are_merged_before_lookup():
    """Unmerged, 180 finds the (150, 160) interval, sees it ended, and escapes."""
    iv = merge([(100, 200), (150, 160)])
    assert iv == [(100, 200)]
    assert impose(np.array([180]), iv).tolist() == [True]


def test_no_outages_hides_nothing():
    assert not impose(np.array([1, 2, 3]), []).any()


def test_error_is_per_station_over_censored_hours_only():
    truth = np.array([10, 10, 50, 0])
    est = np.array([8, 10, 999, 3])
    f = np.array([0.5, 0.0, 0.0, 0.4])
    st = np.array(["a", "a", "a", "b"])
    err = station_error(truth, est, f, st)
    # a: only its first hour was censored -> (8-10)/10. The 999 is uncensored.
    assert err["a"] == -0.2
    # b: censored, but no true departures there -> not scoreable
    assert err["b"] is None


def test_both_thresholds_must_hold():
    assert passes({"median_abs_pct": 20.0, "median_signed_pct": -10.0})
    assert not passes({"median_abs_pct": 20.1, "median_signed_pct": 0.0})
    assert not passes({"median_abs_pct": 5.0, "median_signed_pct": 10.1})


def test_trip_start_times_are_real_epoch_seconds():
    """astype(int64) // 1e9 gave 1787313 here - pandas 2 had stored seconds, not
    nanoseconds - which puts every trip in January 1970 and hides none of them."""
    import pandas as pd
    sys.path.insert(0, str(ROOT / "pipeline"))
    from aggregate_trips import aggregate_member
    df = pd.DataFrame({
        "started_at": ["2026-08-21 08:00:05"], "ended_at": ["2026-08-21 08:10:00"],
        "start_station_id": ["1.01"], "end_station_id": ["2.02"],
        "member_casual": ["member"], "rideable_type": ["classic_bike"]})
    times = []
    aggregate_member(df, {}, times)
    # 08:00:05 in New York, daylight time, is 12:00:05 UTC.
    assert times[0]["t"].tolist() == [1787313605]


def test_constants_match_the_documents():
    prereg = (ROOT / "PREREGISTRATION.md").read_text(encoding="utf-8")
    assert "**≤ {:.0%}**".format(MAX_ABS_ERR) in prereg
    assert "**±{:.0%}**".format(MAX_SIGNED_ERR) in prereg
    spec = (ROOT / "Downfall_M1_Spec.md").read_text(encoding="utf-8")
    assert "at least {} stations".format(MIN_COHORT) in spec
    assert JUDGED == "em"
