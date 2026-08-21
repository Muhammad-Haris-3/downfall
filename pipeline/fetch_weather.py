"""
Hourly weather for New York, over the same window as the trip marts.

Open-Meteo's archive is keyless and free (NFR-1). Requested in UTC rather than
local time so it joins the marts on `hour_utc` directly - the marts already
carry the one time-zone conversion this project makes, and doing a second one
here would be a second chance to get it wrong.

Hourly rather than daily, because the question is not "was it a wet day" but
"was it raining at eight in the morning". A day with an afternoon thunderstorm
and a dry commute is not a wet day for this purpose, and a daily total cannot
tell the two apart.

Usage:  python pipeline/fetch_weather.py
"""

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "marts" / "weather_hourly.parquet"
MANIFEST = ROOT / "data" / "marts" / "manifest_weather.json"

# Midtown Manhattan. The network spans about 33 km north to south, so one point
# is a simplification - and a real one, recorded rather than hidden: rain in the
# Bronx is not rain in Brooklyn. It is defensible here because the question is
# about broad conditions, not about which station got wet.
LAT, LON = 40.7128, -74.0060
START, END = "2024-01-01", "2026-07-31"
FIELDS = ["temperature_2m", "precipitation", "wind_speed_10m", "relative_humidity_2m"]
URL = "https://archive-api.open-meteo.com/v1/archive"


def main():
    q = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON,
        "start_date": START, "end_date": END,
        "hourly": ",".join(FIELDS),
        "timezone": "UTC",
    })
    print("fetching {}..{}".format(START, END))
    req = urllib.request.Request(URL + "?" + q,
                                 headers={"User-Agent": "downfall/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        payload = json.load(r)

    h = payload["hourly"]
    df = pd.DataFrame({
        "hour_utc": pd.to_datetime(h["time"], utc=True),
        "temp_c": h["temperature_2m"],
        "precip_mm": h["precipitation"],
        "wind_kmh": h["wind_speed_10m"],
        "humidity": h["relative_humidity_2m"],
    })

    missing = {c: int(df[c].isna().sum()) for c in df.columns if c != "hour_utc"}
    df = df.dropna(subset=["temp_c", "precip_mm"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False, compression="zstd")

    manifest = {
        "source": "Open-Meteo archive, keyless",
        "point": {"lat": LAT, "lon": LON, "note": "one point for the whole network"},
        "window": [START, END],
        "hours": len(df),
        "missing_before_drop": missing,
        "fields": FIELDS,
        "timezone": "UTC, to join the marts without a second conversion",
        "output": OUT.name,
        "output_bytes": OUT.stat().st_size,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2))

    print("  {:,} hours, {:.2f} MB".format(len(df), OUT.stat().st_size / 1e6))
    print("  temp {:.1f} to {:.1f} C".format(df.temp_c.min(), df.temp_c.max()))
    print("  hours with any rain: {:,} ({:.1f}%)".format(
        int((df.precip_mm > 0).sum()), (df.precip_mm > 0).mean() * 100))
    print("  missing before drop: {}".format(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
