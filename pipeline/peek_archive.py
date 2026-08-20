"""
Read a remote zip's contents without downloading it.

A zip stores its index - the central directory - at the END of the file. So a
range request for the last few hundred kilobytes is enough to list every member
and its uncompressed size. For the 2026-04 question that is 200 KB against
164 MB, and it answers "is this file truncated" directly.

Usage:  python pipeline/peek_archive.py 202603 202604 202605
"""

import struct
import sys
import urllib.request

BUCKET = "https://s3.amazonaws.com/tripdata/"
EOCD_SIG = b"PK\x05\x06"
CEN_SIG = b"PK\x01\x02"
TAIL = 400_000          # comfortably more than a central directory of a few files
BYTES_PER_ROW = 194.9   # calibrated against 2026-02, downloaded and counted in full


def get_range(url, start_from_end):
    req = urllib.request.Request(
        url, headers={"Range": "bytes=-{}".format(start_from_end),
                      "User-Agent": "downfall/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(), r.headers.get("Content-Range")


def parse_central_directory(tail):
    """Yield (name, compressed, uncompressed) for every member."""
    i = tail.rfind(EOCD_SIG)
    if i < 0:
        raise ValueError("no end-of-central-directory found in the tail")
    n_entries = struct.unpack("<H", tail[i + 10:i + 12])[0]

    pos = tail.find(CEN_SIG)
    if pos < 0:
        raise ValueError("central directory starts before the bytes we fetched")

    out = []
    while pos < len(tail) and tail[pos:pos + 4] == CEN_SIG:
        comp, uncomp = struct.unpack("<II", tail[pos + 20:pos + 28])
        n_len, x_len, c_len = struct.unpack("<HHH", tail[pos + 28:pos + 34])
        name = tail[pos + 46:pos + 46 + n_len].decode("utf-8", "replace")
        out.append((name, comp, uncomp))
        pos += 46 + n_len + x_len + c_len
    return n_entries, out


def peek(month):
    url = "{}{}-citibike-tripdata.zip".format(BUCKET, month)
    tail, content_range = get_range(url, TAIL)
    total = int(content_range.split("/")[-1]) if content_range else None
    n_entries, members = parse_central_directory(tail)

    real = [m for m in members if not m[0].startswith("__MACOSX")]
    uncomp = sum(m[2] for m in real)
    # Rows are estimated from bytes, not counted. Calibrated against 2026-02,
    # which was downloaded in full: 237,633,000 bytes / 1,219,444 rows = 194.9.
    print("{}   zip {:>7.1f} MB   csv {:>7.1f} MB   {} files   ~{:>9,.0f} trips".format(
        month, (total or 0) / 1e6, uncomp / 1e6, len(real), uncomp / BYTES_PER_ROW))
    for name, comp, unc in real:
        print("      {:<44} {:>8.1f} MB".format(name, unc / 1e6))
    return {"month": month, "zip_bytes": total, "csv_bytes": uncomp,
            "files": len(real), "entries": n_entries}


if __name__ == "__main__":
    for m in sys.argv[1:]:
        peek(m)
