#!/usr/bin/env python3
"""Summarise NoNap latency CSVs (logs/latency_<date>.csv) for the paper.

Usage:
    python3 tools/latency_report.py                      # every logs/latency_*.csv
    python3 tools/latency_report.py logs/latency_2026-10-21.csv --source pi
    python3 tools/latency_report.py --alerts-only        # only frames that raised/changed an alert

Prints n / mean / median / p95 / min / max for each stage. Only rows that
contain both timestamps of a stage are used; nothing is interpolated.
Standard library only.
"""

import argparse
import csv
import glob
import math
import statistics
import sys

# (label, end column, start column, same clock?)
STAGES = [
    ("Pi round trip (Pi clock)", "pi_rtt_ms", None, True),
    ("Inference (server receive -> inference done)", "inference_ms", None, True),
    ("Server total (receive -> WebSocket sent)", "server_to_ws_ms", None, True),
    ("Uplink (Pi capture -> server receive)*", "server_receive_ms", "pi_capture_ms", False),
    ("Downlink (WebSocket sent -> app received)*", "app_received_ms", "ws_sent_ms", False),
    ("End to end (Pi capture -> app received)*", "app_received_ms", "pi_capture_ms", False),
]


def num(v):
    try:
        return float(v) if v not in ("", None) else None
    except ValueError:
        return None


def pct(values, p):
    if not values:
        return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * p / 100.0
    lo, hi = math.floor(k), math.ceil(k)
    return s[int(k)] if lo == hi else s[lo] + (s[hi] - s[lo]) * (k - lo)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="CSV files (default: logs/latency_*.csv)")
    ap.add_argument("--source", choices=["pi", "simulated", "webcam", "video"], help="only rows from this source")
    ap.add_argument("--alerts-only", action="store_true", help="only rows that carried an alert event")
    ap.add_argument("--csv", action="store_true", help="print the summary as CSV")
    args = ap.parse_args()

    files = args.files or sorted(glob.glob("logs/latency_*.csv"))
    if not files:
        sys.exit("No latency CSVs found. Run the system first (they are written to logs/).")

    rows = []
    for path in files:
        with open(path, newline="") as f:
            rows.extend(csv.DictReader(f))
    if args.source:
        rows = [r for r in rows if r.get("source") == args.source]
    if args.alerts_only:
        rows = [r for r in rows if r.get("alert_id")]

    print(f"Files: {', '.join(files)}")
    print(f"Rows:  {len(rows)}" + (f" (source={args.source})" if args.source else ""))
    print()

    out = []
    for label, end_col, start_col, _same_clock in STAGES:
        vals = []
        for r in rows:
            end = num(r.get(end_col))
            if end is None:
                continue
            if start_col is None:
                vals.append(end)
            else:
                start = num(r.get(start_col))
                if start is not None:
                    vals.append(end - start)
        out.append((label, vals))

    if args.csv:
        print("stage,n,mean_ms,median_ms,p95_ms,min_ms,max_ms")
        for label, v in out:
            if v:
                print(f"\"{label}\",{len(v)},{statistics.mean(v):.2f},{statistics.median(v):.2f},"
                      f"{pct(v, 95):.2f},{min(v):.2f},{max(v):.2f}")
            else:
                print(f"\"{label}\",0,,,,,")
        return

    w = max(len(label) for label, _ in out)
    print(f"{'Stage'.ljust(w)}  {'n':>6}  {'mean':>8}  {'median':>8}  {'p95':>8}  {'min':>8}  {'max':>8}")
    for label, v in out:
        if v:
            print(f"{label.ljust(w)}  {len(v):>6}  {statistics.mean(v):>8.1f}  {statistics.median(v):>8.1f}  "
                  f"{pct(v, 95):>8.1f}  {min(v):>8.1f}  {max(v):>8.1f}")
        else:
            print(f"{label.ljust(w)}  {0:>6}  {'-':>8}  {'-':>8}  {'-':>8}  {'-':>8}  {'-':>8}")
    print()
    print("All values in milliseconds.")
    print("* Crosses two device clocks; includes their offset. Keep the Pi, Mac and iPhone on NTP")
    print("  and report these together with the measured offset (see docs/PAPER_NOTES.md).")


if __name__ == "__main__":
    main()
