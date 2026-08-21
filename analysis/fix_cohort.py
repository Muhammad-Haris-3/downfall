"""
Fix the top-200 cohort, once, from months that precede the measurement window.

`PREREGISTRATION.md` §6 and `Downfall_M1_Spec.md` §5.1 name "the top 200 stations
by departures" as the population the kill criterion is evaluated on. Which 200
those are has to be settled before the censoring figure exists, for a reason that
is not bureaucratic:

  Selecting the cohort from the same period whose censoring is being measured
  picks stations partly on the outcome. A station that stocked out a lot in the
  window recorded fewer departures in the window, so it would be less likely to
  enter a cohort defined on that window - and the exposure figure computed over
  the survivors would be biased. Defining it on the twelve months BEFORE
  collection began removes that path entirely.

The output carries a SHA-256 over the sorted station list. If a later analysis
uses a cohort with a different digest, it is not this cohort, and no amount of
prose in a commit message changes that.

Run once. Refuses to overwrite.

Usage:  python analysis/fix_cohort.py [--force]
"""

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MARTS = ROOT / "data" / "marts"
OUT = ROOT / "data" / "cohort_top200.json"

# The twelve complete months preceding the start of outage collection
# (2026-08-20). Listed rather than computed, so the window cannot drift.
WINDOW = ["202508", "202509", "202510", "202511", "202512",
          "202601", "202602", "202603", "202604", "202605", "202606", "202607"]
N = 200


def main():
    if OUT.exists() and "--force" not in sys.argv:
        print("{} already exists. The cohort is fixed once.".format(OUT.name))
        print("Re-deriving it after the exposure figure is known is the exact")
        print("thing this file exists to prevent. Use --force only to correct a")
        print("cohort that was never used.")
        return 1

    missing = [m for m in WINDOW if not (MARTS / "trip_counts_{}.parquet".format(m)).exists()]
    if missing:
        print("missing marts: {}".format(missing))
        return 1

    total = None
    for m in WINDOW:
        df = pd.read_parquet(MARTS / "trip_counts_{}.parquet".format(m),
                             columns=["station", "departures"])
        s = df.groupby("station")["departures"].sum()
        total = s if total is None else total.add(s, fill_value=0)
    total = total.sort_values(ascending=False).astype("int64")

    # Ties at the boundary are broken by station id, so the cohort is a pure
    # function of the data and not of pandas' sort stability across versions.
    cut = total.iloc[N - 1]
    at_cut = total[total == cut]
    chosen = list(total[total > cut].index) + sorted(at_cut.index)
    chosen = chosen[:N]

    digest = hashlib.sha256("\n".join(sorted(chosen)).encode()).hexdigest()
    payload = {
        "rule": ("top {} stations by total departures across {}..{}, the twelve "
                 "complete months preceding outage collection; ties broken by "
                 "station id").format(N, WINDOW[0], WINDOW[-1]),
        "window": WINDOW,
        "n": len(chosen),
        "sha256": digest,
        "departures_threshold": int(cut),
        "stations": sorted(chosen),
    }
    OUT.write_text(json.dumps(payload, indent=1))

    print("cohort fixed: {} stations".format(len(chosen)))
    print("  window        {} .. {}".format(WINDOW[0], WINDOW[-1]))
    print("  network total {:,} stations with any departure".format(len(total)))
    print("  cohort share  {:.1f}% of all departures".format(
        total.loc[chosen].sum() / total.sum() * 100))
    print("  entry cutoff  {:,} departures over twelve months".format(int(cut)))
    print("  busiest       {:,}".format(int(total.iloc[0])))
    print("  sha256        {}".format(digest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
