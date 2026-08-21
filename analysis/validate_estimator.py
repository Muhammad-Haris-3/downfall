"""
Mark the estimator against cases where the answer is already known.

This is the preliminary form of the validation fixed in `PREREGISTRATION.md` §4.
It differs in one way that is stated rather than glossed:

  §4 requires synthetic censoring drawn from the OBSERVED outage pattern of a
  matched station. That needs an outage record deeper than currently exists, so
  the patterns here are generated instead. **This run cannot satisfy §4 and is
  not claimed to.** What it can do is establish whether the method works at all,
  before there is any exposure figure to want it to.

Building it now is the safest moment: there is no result yet to steer toward.

TWO CENSORING REGIMES, and the gap between them is the point
------------------------------------------------------------
  UNIFORM        The censored minutes are placed at random. Demand during them
                 is the same as demand outside them. This is the easy case, and
                 the one a naive division by (1-f) is built for.

  DEMAND-DRIVEN  The station runs out BECAUSE demand was heavy, so the censored
                 minutes are the busy ones. This is what actually happens, and
                 it is where dividing by (1-f) understates - because the minutes
                 it is scaling up from were the quiet ones.

A method that does well on uniform and badly on demand-driven has learned the
test, not the problem. Both are reported.

Usage:  python analysis/validate_estimator.py [n_months] [n_stations]
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis.unconstrain import METHODS                        # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MARTS = ROOT / "data" / "marts"
COHORT = ROOT / "data" / "cohort_top200.json"

SEED = 20260821
# Pre-registration §4 thresholds. Named here so the report states the bar it is
# being held to, in the same output as the result.
MAX_ABS_ERR = 0.20
MAX_SIGNED_ERR = 0.10


def load(months, stations=None):
    frames = []
    for m in months:
        p = MARTS / "trip_counts_{}.parquet".format(m)
        df = pd.read_parquet(p, columns=["station", "hour_utc", "departures",
                                         "arrivals", "hour_local", "dow_local"])
        if stations is not None:
            df = df[df["station"].isin(stations)]
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def censor_uniform(rng, truth, p_hour, f_mean):
    """Censored minutes fall at random. Demand inside them is ordinary."""
    n = len(truth)
    censored = rng.random(n) < p_hour
    f = np.where(censored, rng.beta(2.0, 2.0 * (1 - f_mean) / f_mean, n), 0.0)
    f = np.clip(f, 0.0, 0.98)
    # Each would-be departure independently either found a bike or did not.
    observed = rng.binomial(truth.astype(int), 1.0 - f)
    return observed, f


def censor_demand_driven(rng, truth, p_hour, f_mean, arrivals=None, slots=60):
    """The station runs out because it was busy - simulated minute by minute.

    An earlier version of this function computed `f = lost / truth` directly.
    That made `observed = truth * (1 - f)` true by construction, which is
    precisely what `scaled` inverts - so `scaled` scored 4.7% on a test that had
    been handed the answer. The result looked like the method working and was
    the simulator marking its own homework.

    This version simulates the mechanism instead. Demand and returns are spread
    across the minutes of the hour, stock is walked forward, and a departure
    that arrives at an empty dock is lost. **Both `observed` and `f` are outputs
    of that process**, related through it but not by an identity the estimator
    can exploit.
    """
    n = len(truth)
    if arrivals is None:
        arrivals = np.zeros(n, dtype=int)

    # Opening stock. Set so roughly the intended share of hours run dry, with
    # busy hours far likelier to be among them - which is the realistic part.
    scale = np.quantile(truth[truth > 0], 1.0 - p_hour) if (truth > 0).any() else 1.0
    stock = rng.poisson(np.maximum(scale, 1.0), n).astype(np.int64)

    # Spread each hour's demand and returns across its minutes. Uniform within
    # the hour is an assumption, but it is not the assumption under test.
    dep = rng.multinomial(np.maximum(truth, 0).astype(int),
                          np.full(slots, 1.0 / slots))
    arr = rng.multinomial(np.maximum(arrivals, 0).astype(int),
                          np.full(slots, 1.0 / slots))

    served = np.zeros(n, dtype=np.int64)
    empty_slots = np.zeros(n, dtype=np.int64)
    for t in range(slots):
        stock += arr[:, t]
        take = np.minimum(dep[:, t], stock)
        served += take
        stock -= take
        # A minute counts as empty if there was nothing there to take during it.
        empty_slots += (stock <= 0)

    return served, empty_slots / slots


REGIMES = {"uniform": censor_uniform, "demand-driven": censor_demand_driven}


def score(truth, est, mask):
    """Median absolute and median signed percentage error, over censored hours.

    Scored only where censoring happened. Everywhere else every method returns
    the observed count unchanged, and including those rows would dilute the
    comparison with agreement that was never in question.
    """
    t = truth[mask].astype(float)
    e = est[mask].astype(float)
    keep = t > 0
    if keep.sum() == 0:
        return None
    pe = (e[keep] - t[keep]) / t[keep]
    return {"n": int(keep.sum()),
            "median_abs_pct": float(np.median(np.abs(pe)) * 100),
            "median_signed_pct": float(np.median(pe) * 100),
            "mean_signed_pct": float(np.mean(pe) * 100)}


def main(n_months=6, n_stations=200):
    months = sorted(p.stem.replace("trip_counts_", "")
                    for p in MARTS.glob("trip_counts_*.parquet"))[-n_months:]
    cohort = json.loads(COHORT.read_text())["stations"][:n_stations]

    df = load(months, set(cohort))
    df = df.sort_values(["station", "hour_utc"]).reset_index(drop=True)
    truth = df["departures"].to_numpy()

    print("months     {} .. {}".format(months[0], months[-1]))
    print("stations   {}".format(df["station"].nunique()))
    print("hours      {:,}".format(len(df)))
    print("thresholds median abs <= {:.0f}%, median signed within +/-{:.0f}%  "
          "(PREREGISTRATION.md §4)\n".format(MAX_ABS_ERR * 100, MAX_SIGNED_ERR * 100))

    arrivals = df["arrivals"].to_numpy()
    rows = []
    for regime, fn in REGIMES.items():
        rng = np.random.default_rng(SEED)
        kw = {"arrivals": arrivals} if regime == "demand-driven" else {}
        observed, f = fn(rng, truth, p_hour=0.15, f_mean=0.35, **kw)
        mask = f > 0
        work = df.copy()
        work["departures"] = observed
        work["empty_frac"] = f

        print("=== {} censoring ===  {:,} hours censored ({:.1f}%), "
              "mean f {:.2f}".format(regime, int(mask.sum()),
                                     mask.mean() * 100, f[mask].mean()))
        print("  {:<10}{:>8}{:>16}{:>18}".format(
            "method", "n", "median |err|", "median signed"))
        for name, method in METHODS.items():
            est = method(work) if name != "naive" else work["departures"].to_numpy(float)
            s = score(truth, est, mask)
            passes = (s["median_abs_pct"] <= MAX_ABS_ERR * 100
                      and abs(s["median_signed_pct"]) <= MAX_SIGNED_ERR * 100)
            print("  {:<10}{:>8,}{:>15.1f}%{:>17.1f}%   {}".format(
                name, s["n"], s["median_abs_pct"], s["median_signed_pct"],
                "PASS" if passes else ""))
            rows.append(dict(regime=regime, method=name, **s, passes=passes))
        print()

    out = ROOT / "data" / "validation_preliminary.json"
    out.write_text(json.dumps(
        {"note": ("preliminary: censoring patterns are generated, not drawn from "
                  "observed outages, so this does NOT satisfy PREREGISTRATION.md "
                  "§4"),
         "months": months, "seed": SEED, "results": rows}, indent=1))
    print("-> {}".format(out.name))
    return 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 6,
                  int(sys.argv[2]) if len(sys.argv) > 2 else 200))
