"""Tests for the M1 gate.

Two kinds. The band logic, which decides whether the project continues; and a
set that asserts the numbers in the code are the numbers in the documents a
reader will hold the project to. A pre-registration that has drifted out of the
code it governs is decoration.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.exposure import (BAND_KILL, BAND_NARROW, REQUIRED_COVERAGE,  # noqa: E402
                               REQUIRED_DAYS, REQUIRED_OUTAGES,
                               REQUIRED_SLOT_OBSERVATIONS, band_for)

ROOT = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------------- the bands

def test_below_two_percent_kills_the_project():
    assert band_for(0.0) == "KILL"
    assert band_for(0.019) == "KILL"


def test_between_two_and_ten_percent_narrows_it():
    assert band_for(0.02) == "NARROW"
    assert band_for(0.099) == "NARROW"


def test_ten_percent_or_more_proceeds_as_specified():
    assert band_for(0.10) == "PROCEED"
    assert band_for(0.5) == "PROCEED"


def test_the_boundaries_belong_to_the_higher_band():
    """Exactly 2% is NARROW, not KILL; exactly 10% is PROCEED, not NARROW.

    Stated so that a boundary case cannot be argued either way later.
    """
    assert band_for(BAND_KILL) == "NARROW"
    assert band_for(BAND_NARROW) == "PROCEED"


def test_a_straddling_interval_is_governed_by_its_lower_bound():
    """M1 spec §6: the conservative band governs.

    A point estimate of 10.4% with an interval reaching 8% is a NARROW result,
    because the evidence does not exclude the narrower conclusion.
    """
    point, lower = 0.104, 0.08
    assert band_for(point) == "PROCEED"
    assert band_for(lower) == "NARROW"
    governing = band_for(lower)
    assert governing == "NARROW"


# ------------------------------------------ the code agrees with the documents

def test_floor_constants_match_the_preregistration():
    text = (ROOT / "PREREGISTRATION.md").read_text(encoding="utf-8")
    assert "{} days".format(REQUIRED_DAYS) in text
    assert "{:.0%}".format(REQUIRED_COVERAGE) in text
    assert "{:,}".format(REQUIRED_OUTAGES) in text
    assert "168 hour-of-week" in text
    assert str(REQUIRED_SLOT_OBSERVATIONS) in text


def test_band_constants_match_the_m1_spec():
    text = (ROOT / "Downfall_M1_Spec.md").read_text(encoding="utf-8")
    assert "{:.0%}".format(BAND_KILL) in text
    assert "{:.0%}".format(BAND_NARROW) in text
    assert "conservative band governs" in text


def test_the_cohort_file_matches_its_own_digest():
    """The cohort is identified by a hash so that an analysis quoting a
    different one is visibly not quoting this cohort."""
    import hashlib
    payload = json.loads((ROOT / "data" / "cohort_top200.json").read_text())
    digest = hashlib.sha256("\n".join(sorted(payload["stations"])).encode()).hexdigest()
    assert digest == payload["sha256"]
    assert payload["n"] == 200


def test_the_cohort_window_ends_before_collection_began():
    """The whole point of the cohort rule.

    Ranking stations on the same window whose censoring is measured selects
    partly on the outcome: a station that stocked out heavily recorded fewer
    departures and would be less likely to qualify.
    """
    payload = json.loads((ROOT / "data" / "cohort_top200.json").read_text())
    assert max(payload["window"]) <= "202607", "cohort window overlaps collection"
