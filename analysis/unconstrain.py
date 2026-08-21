"""
Recovering demand from a series that could not record it.

THE PROBLEM
-----------
A station-hour records D departures. If the station had no bikes for a fraction
f of that hour, D is not the demand - it is the demand that arrived while there
was something to take. The rest left no trace of any kind.

THREE METHODS, and the first two are here to be beaten:

  NAIVE          lambda = D.  Do nothing. This is what essentially every
                 published analysis of this dataset does, and it is the thing
                 the project claims is wrong. It has to be in the comparison or
                 there is no comparison.

  SCALED         lambda = D / (1 - f).  The obvious correction: if bikes were
                 there for 40% of the hour, multiply by 2.5. Simple, and biased
                 - see below - but a real improvement over doing nothing, and
                 any complicated method that cannot beat it is not worth having.

  EM             Departures ~ Poisson(level[station] * shape[hour-of-week]).
                 Fit on what was observable, use the fitted rate to fill in the
                 unobservable part, refit, repeat. The station's own behaviour in
                 comparable hours supplies what the censored hour could not.

WHY SCALED IS BIASED, AND WHY IT IS BIASED THE SAFE WAY
-------------------------------------------------------
Dividing by (1 - f) assumes demand is spread evenly across the hour. It is not: a
station runs out BECAUSE demand was heavy, so the censored minutes are
disproportionately the busy ones. The correction therefore recovers too little.

That direction matters. **Both corrections here understate**, so a finding that
survives them survives conservatively. A method that overstated would manufacture
exactly the result this project is looking for, which is why the pre-registration
requires the signed error to be checked and not only the absolute one.

WHAT NONE OF THIS RECOVERS
--------------------------
Someone who checked an app, saw an empty station and never left home. That person
is in no dataset and never will be. What is estimated here is departures that
would have occurred from a stocked dock, and it is never called anything else.
"""

import numpy as np
import pandas as pd

EPS = 1e-9
# Above this, the hour carries almost no information and dividing by (1-f)
# amplifies whatever noise is left into a number with no content. Such hours are
# still ESTIMATED - by the profile alone - but never by scaling.
MAX_SCALE_F = 0.9


def hour_of_week(hour_utc_local_dow, hour_local):
    return hour_utc_local_dow * 24 + hour_local


def naive(df):
    """What everyone does. The comparison, not a contender."""
    return df["departures"].astype(float).to_numpy()


def scaled(df, f_col="empty_frac"):
    """Divide by the share of the hour a bike was available."""
    f = np.clip(df[f_col].to_numpy(dtype=float), 0.0, MAX_SCALE_F)
    return df["departures"].to_numpy(dtype=float) / np.maximum(1.0 - f, EPS)


def em(df, f_col="empty_frac", iters=25, tol=1e-5):
    """Poisson level x hour-of-week shape, fitted by expectation-maximisation.

    Returns the expected true departures for every row.

    The E-step is the whole idea in one line: an hour that was open for 40% of
    its length contributes its observed count plus the rate the model expects for
    the 60% nobody could see. The M-step then refits level and shape on those
    completed counts, so a heavily censored hour stops dragging the station's own
    profile downward - which is the feedback loop the project is about, appearing
    inside the estimator.
    """
    d = df["departures"].to_numpy(dtype=float)
    f = np.clip(df[f_col].to_numpy(dtype=float), 0.0, 1.0)
    open_frac = np.maximum(1.0 - f, EPS)

    st_idx, st_keys = pd.factorize(df["station"], sort=True)
    # Cast BEFORE multiplying. The marts store dow_local as int8 to keep 30M
    # rows small, and 6 * 24 = 144 overflows int8 to -112 - which np.bincount
    # rejects, loudly, only because it happens to refuse negatives. A slightly
    # different expression would have silently mixed Saturday into Wednesday.
    dow = df["dow_local"].to_numpy().astype(np.int32)
    hod = df["hour_local"].to_numpy().astype(np.int32)
    how = dow * 24 + hod
    n_st, n_how = len(st_keys), 168

    # Start from the naive counts. Any starting point converges; this one makes
    # the first iteration interpretable.
    complete = d.copy()
    level = np.ones(n_st)
    shape = np.ones(n_how)

    for it in range(iters):
        # ---- M-step: level and shape from the currently completed counts.
        # Two passes of a multiplicative update - the standard fit for a
        # rank-one Poisson mean, and enough at this size.
        for _ in range(2):
            num = np.bincount(st_idx, weights=complete, minlength=n_st)
            den = np.bincount(st_idx, weights=shape[how], minlength=n_st)
            level = num / np.maximum(den, EPS)

            num = np.bincount(how, weights=complete, minlength=n_how)
            den = np.bincount(how, weights=level[st_idx], minlength=n_how)
            shape = num / np.maximum(den, EPS)

        rate = level[st_idx] * shape[how]

        # ---- E-step: observed part, plus the model's expectation for the part
        # that could not be observed.
        new_complete = d + rate * f

        # An uncensored hour is data, not a fitted value. Never let the model
        # overwrite something that was actually measured.
        new_complete = np.where(f <= EPS, d, new_complete)

        if np.max(np.abs(new_complete - complete)) < tol:
            complete = new_complete
            break
        complete = new_complete

    return complete


METHODS = {"naive": naive, "scaled": scaled, "em": em}
