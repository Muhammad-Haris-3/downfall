"""
Which months still need aggregating?

Lists the bucket, subtracts the months for which a manifest already exists, and
prints the remainder as a JSON array for a workflow matrix.

A manifest is the test, not the mart: a mart without one has no record of what
was dropped on the way in, and is therefore not usable. See SRS FR-14.

Usage:
  python pipeline/list_months.py            # months with no manifest
  python pipeline/list_months.py --all      # every month in the bucket
"""

import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARTS = ROOT / "data" / "marts"
BUCKET = "https://s3.amazonaws.com/tripdata/"
NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}


def bucket_months():
    req = urllib.request.Request(BUCKET, headers={"User-Agent": "downfall/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        root = ET.fromstring(r.read())
    months = []
    for c in root.findall("s3:Contents", NS):
        key = c.find("s3:Key", NS).text
        # Jersey City is a separate, much smaller system and is out of scope.
        # Yearly archives (2013-2023) are a later extension, not this pipeline.
        if key.startswith("JC-") or not key.endswith(".zip"):
            continue
        m = re.match(r"^(\d{6})-citibike-tripdata\.zip$", key)
        if m:
            months.append(m.group(1))
    return sorted(months)


def main():
    months = bucket_months()
    if "--all" not in sys.argv:
        done = {p.stem.replace("manifest_", "") for p in MARTS.glob("manifest_*.json")}
        months = [m for m in months if m not in done]
    print(json.dumps(months))


if __name__ == "__main__":
    main()
