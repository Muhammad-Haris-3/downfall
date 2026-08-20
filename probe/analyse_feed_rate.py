"""
M0-T1 analysis - turn the raw polls into the refresh interval.

Three separate questions, deliberately not mixed:

  1. REFRESH   How long between two different `last_reported` values for one
               station? This is the finest interval a stockout can be seen in.
  2. STALENESS When we read a value, how old is it already? Our poll clock and
               the feed's clock are not the same clock.
  3. SHAPE     Do all stations refresh together on one heartbeat, or each on its
               own? A batched feed is described by one number; an independent one
               is not, and would need a different collector.
"""

import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

RAW = Path(__file__).resolve().parent.parent / "data" / "feed_rate_raw.jsonl.gz"
I_LAST_REPORTED = 5          # position of last_reported in the KEEP tuple
I_BIKES = 0


def pct(sorted_vals, p):
    if not sorted_vals:
        return float("nan")
    k = max(0, min(len(sorted_vals) - 1, int(round(p / 100 * (len(sorted_vals) - 1)))))
    return sorted_vals[k]


def main():
    polls, errors, header = [], 0, None
    with gzip.open(RAW, "rt", encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if rec["kind"] == "poll":
                polls.append(rec)
            elif rec["kind"] == "error":
                errors += 1
            else:
                header = rec

    span = polls[-1]["wall"] - polls[0]["wall"]
    print(f"polls: {len(polls)}   failed: {errors}   "
          f"tick: {header['tick_s']}s   span: {span/60:.1f} min")
    print(f"stations per poll: {len(polls[0]['stations'])}\n")

    # ---- 1. REFRESH -------------------------------------------------------
    # Walk each station's series and collect the gaps between changed readings.
    last_seen = {}
    gaps = []
    changed_per_poll = []
    for i, rec in enumerate(polls):
        changed = 0
        for sid, vals in rec["stations"].items():
            lr = vals[I_LAST_REPORTED]
            prev = last_seen.get(sid)
            if prev is None:
                last_seen[sid] = lr
                continue
            if lr != prev:
                gaps.append(lr - prev)
                last_seen[sid] = lr
                changed += 1
        if i:
            changed_per_poll.append(changed)

    gaps.sort()
    n_stations = len(polls[0]["stations"])
    print("1. REFRESH INTERVAL  (seconds between two different readings)")
    if gaps:
        print(f"   samples: {len(gaps)}")
        for p in (10, 25, 50, 75, 90, 99):
            print(f"   p{p:<2}: {pct(gaps, p):>8.0f}s")
        print(f"   most common: "
              + ", ".join(f"{v}s x{c}" for v, c in Counter(gaps).most_common(5)))
    else:
        print("   NO STATION CHANGED - feed is slower than the whole run")

    # ---- 2. STALENESS -----------------------------------------------------
    stale = []
    for rec in polls:
        for vals in rec["stations"].values():
            stale.append(rec["wall"] - vals[I_LAST_REPORTED])
    stale.sort()
    print("\n2. STALENESS AT READ TIME  (how old the value already is)")
    for p in (10, 50, 90, 99):
        print(f"   p{p:<2}: {pct(stale, p):>8.0f}s")

    # ---- 3. SHAPE ---------------------------------------------------------
    print("\n3. SHAPE")
    print(f"   stations whose reading changed, per poll: "
          f"min {min(changed_per_poll)}, median {median(changed_per_poll):.0f}, "
          f"max {max(changed_per_poll)}  (of {n_stations})")
    # If the feed is batched, most stations in a poll share one last_reported.
    batching = []
    for rec in polls:
        c = Counter(v[I_LAST_REPORTED] for v in rec["stations"].values())
        batching.append(c.most_common(1)[0][1] / n_stations)
    print(f"   share of stations sharing the single most common timestamp: "
          f"median {median(batching)*100:.0f}%")

    # ---- bonus: did we see any real stockout movement? --------------------
    moved = defaultdict(int)
    for a, b in zip(polls, polls[1:]):
        for sid, vb in b["stations"].items():
            va = a["stations"].get(sid)
            if va and va[I_BIKES] != vb[I_BIKES]:
                moved[sid] += 1
    print(f"\n   stations whose bike count moved at least once: {len(moved)} "
          f"of {n_stations}")


if __name__ == "__main__":
    main()
