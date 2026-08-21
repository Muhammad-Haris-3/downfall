"""Tests for the demand estimator.

The estimator's failure mode is not a crash - it is a number that looks fine.
These check the properties that would have to hold for any correct method, plus
one regression for a bug that only surfaced because numpy happened to be strict.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.unconstrain import em, naive, scaled  # noqa: E402


def frame(departures, empty_frac, dow=None, hour=None, station="a"):
    n = len(departures)
    return pd.DataFrame({
        "station": [station] * n if isinstance(station, str) else station,
        "departures": np.asarray(departures),
        "empty_frac": np.asarray(empty_frac, dtype=float),
        # int8 on purpose: this is how the marts store them, and it is where the
        # overflow below came from.
        "dow_local": np.asarray(dow if dow is not None else [0] * n, dtype="int8"),
        "hour_local": np.asarray(hour if hour is not None else list(range(n)),
                                 dtype="int8"),
    })


# ------------------------------------------------------------ basic properties

def test_naive_returns_the_observed_count_unchanged():
    df = frame([5, 0, 12], [0.5, 0.0, 0.9])
    assert list(naive(df)) == [5, 0, 12]


def test_scaled_doubles_when_half_the_hour_was_unavailable():
    df = frame([10], [0.5])
    assert scaled(df)[0] == pytest.approx(20.0)


def test_scaled_is_capped_so_a_fully_empty_hour_does_not_explode():
    """At f = 1 the hour carries no information and 1/(1-f) is infinite.
    A number produced there would be noise with a decimal point."""
    df = frame([3], [1.0])
    assert np.isfinite(scaled(df)[0])
    assert scaled(df)[0] <= 3 / (1 - 0.9) + 1e-6


def test_an_uncensored_hour_is_never_altered_by_any_method():
    """Uncensored counts are measurements. A model that overwrites them has
    stopped estimating the missing part and started editing the observed one."""
    df = frame([7, 4, 9], [0.0, 0.0, 0.0])
    for method in (naive, scaled, em):
        assert list(np.round(method(df), 6)) == [7.0, 4.0, 9.0]


def test_every_method_returns_at_least_what_was_observed():
    """Demand cannot be lower than the departures that actually happened."""
    rng = np.random.default_rng(0)
    d = rng.poisson(6, 300)
    f = rng.random(300) * 0.8
    df = frame(d, f, dow=rng.integers(0, 7, 300), hour=rng.integers(0, 24, 300))
    for method in (scaled, em):
        assert np.all(method(df) >= d - 1e-6), method.__name__


# ------------------------------------------------------------------ regression

def test_day_six_does_not_overflow_into_a_negative_hour_of_week():
    """dow_local is int8 in the marts, and 6 * 24 = 144 overflows to -112.

    np.bincount refused it, loudly, which is the only reason this was caught.
    A slightly different expression would have silently folded Saturday's hours
    into Wednesday's and produced a perfectly plausible profile.
    """
    n = 7 * 24
    df = frame(
        departures=np.arange(n) % 5 + 1,
        empty_frac=[0.4] * n,
        dow=[d for d in range(7) for _ in range(24)],
        hour=list(range(24)) * 7,
    )
    out = em(df)
    assert np.all(np.isfinite(out))
    assert np.all(out > 0)


def test_em_uses_the_station_profile_to_fill_a_censored_hour():
    """A station with a strong weekly shape, censored in one slot.

    The estimate for the censored hour should be pulled toward what that slot
    looks like on other weeks - not left at the depressed observed count, which
    is the whole point of having a profile.
    """
    dows, hours, dep, f = [], [], [], []
    for week in range(8):
        for h in range(24):
            dows.append(1)
            hours.append(h)
            busy = 40 if h == 8 else 4
            # The final week's 08:00 is censored and reads far too low.
            if week == 7 and h == 8:
                dep.append(10)
                f.append(0.75)
            else:
                dep.append(busy)
                f.append(0.0)
    df = frame(dep, f, dow=dows, hour=hours)
    out = em(df)
    censored = [i for i, x in enumerate(f) if x > 0][0]
    assert out[censored] > 20, "the profile was not used to fill the gap"


def test_stations_do_not_borrow_each_others_levels():
    """A quiet station next to a busy one must not be inflated by it."""
    n = 48
    df = frame(
        departures=[50] * n + [2] * n,
        empty_frac=[0.0] * n + [0.5] * n,
        dow=[0] * (2 * n),
        hour=list(range(24)) * 4,
        station=["busy"] * n + ["quiet"] * n,
    )
    out = em(df)
    assert out[n:].max() < 20, "the quiet station inherited the busy one's level"
