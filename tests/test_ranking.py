"""The §5 ranking test, which is run once and cannot be re-done if it was wrong."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.ranking import permutation_p, rank_desc, slope  # noqa: E402


def test_rank_one_is_most_demand_and_ties_cannot_fake_a_move():
    assert list(rank_desc([10, 30, 20])) == [3, 1, 2]
    # Two stations level on departures share a rank; one pulling ahead on the
    # estimate moves by half a place, not a whole one.
    assert list(rank_desc([5, 5])) == [1.5, 1.5]


def test_permutation_p_separates_signal_from_noise():
    rng = np.random.default_rng(0)
    x = rng.random(300)
    assert permutation_p(x, 3 * x + rng.normal(0, .1, 300), 500, 1) < 0.01
    # One-sided: a strong NEGATIVE association is not evidence for the claim.
    assert permutation_p(x, -3 * x, 500, 1) > 0.99
    assert abs(slope(x, 2 * x + 1) - 2) < 1e-9
