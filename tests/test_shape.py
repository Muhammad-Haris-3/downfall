"""The concentration figure M4 will lean on.

Gini is the number that says whether a few trucks could move the problem. It is
easy to get subtly wrong, and the way it goes wrong - dropping stations that
never ran out - makes censoring look MORE spread, which would argue against the
very intervention M4 is meant to size.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.shape import gini, top_share  # noqa: E402


def test_gini_bounds():
    assert gini([5, 5, 5, 5]) == 0
    # All in one of n stations: (n-1)/n, not 1, for finite n.
    assert abs(gini([0, 0, 0, 10]) - 0.75) < 1e-12


def test_zeros_raise_concentration():
    # The stations that never ran out are part of the population. Leaving them
    # out answers "how concentrated among the affected", a smaller question.
    assert gini([0, 0, 1, 3]) > gini([1, 3])


def test_top_share():
    assert top_share([1] * 9 + [91], 0.10) == 0.91
