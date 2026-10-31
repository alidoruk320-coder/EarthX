#!/usr/bin/env python3
"""Reproduce Mann–Kendall behavior for synthetic and captured frontend series.

Usage:
  backend/.venv312/bin/python scripts/diagnose_mann_kendall.py
  backend/.venv312/bin/python scripts/diagnose_mann_kendall.py path/to/network-response.json --start-year 2002 --end-year 2025

The optional JSON may be an /api/analyze-point, /api/analyze-series, or
/api/analyze-region response, or a bare list of {year, value} observations.
"""

import json
import math
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.trend_engine import analyze_annual_series


def extract_series(payload):
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("raw_series") or payload.get("series") or []
    else:
        raise ValueError("Expected a JSON list or analysis response object")
    parsed = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        year = row.get("year")
        if year is None and row.get("date"):
            year = str(row["date"])[:4]
        value = row.get("value")
        try:
            year, value = int(year), float(value)
        except (TypeError, ValueError, OverflowError):
            continue
        if math.isfinite(value):
            parsed.append((year, value))
    return parsed


def make_cases():
    years = list(range(2002, 2026))
    signal = [0.31 + index * 0.002 + ((index % 5) - 2) * 0.0007 for index in range(24)]
    complete = list(zip(years, signal))
    missing_middle = [row for row in complete if row[0] != 2011]
    missing_ends = [row for row in complete if row[0] not in {2002, 2025}]
    flat = [(year, 0.4) for year in years]
    ties = [(year, round(value, 2)) for year, value in complete]
    partial_final = complete[:-1] + [(2026, signal[-1] + 0.0002)]
    short = complete[:7]
    return {
        "24 consecutive (small trend)": (complete, 2002, 2025),
        "one missing middle year": (missing_middle, 2002, 2025),
        "missing first and last year": (missing_ends, 2002, 2025),
        "constant series": (flat, 2002, 2025),
        "many tied values": (ties, 2002, 2025),
        "new partial final year included": (partial_final, 2002, 2026),
        "fewer than eight observations": (short, 2002, 2008),
    }


def summarize(label, series, start, end):
    result = analyze_annual_series(
        series,
        expected_start_year=start,
        expected_end_year=end,
    )
    print(
        f"{label}: n={result['observation_count']} period={result['period']} "
        f"Sen={result['sen_slope']} Z={result['z_score']} "
        f"p={result['p_value']} direction={result['trend']} "
        f"test={result['test_status']} method={result['test_method']}"
    )
    if result.get("message"):
        print(f"  note: {result['message']}")
    return result


def main():
    print("Synthetic Mann–Kendall cases (same backend function as /api/analyze-series):")
    for label, (series, start, end) in make_cases().items():
        summarize(label, series, start, end)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_file", nargs="?", help="Captured browser Network JSON response")
    parser.add_argument("--start-year", type=int, help="Requested analysis start year")
    parser.add_argument("--end-year", type=int, help="Requested analysis end year")
    args = parser.parse_args()
    if args.json_file:
        path = Path(args.json_file)
        payload = json.loads(path.read_text(encoding="utf-8"))
        actual = extract_series(payload)
        print(f"\nCaptured frontend/backend series from {path}:")
        if isinstance(payload, dict):
            print(f"API stats in payload: {json.dumps({key: payload.get(key) for key in ('trend', 'sen_slope', 'z_score', 'p_value', 'significant', 'test_status', 'test_method')}, ensure_ascii=False)}")
        if not actual:
            raise SystemExit("No finite annual {year, value} observations found in the JSON")
        expected_start = args.start_year if args.start_year is not None else actual[0][0]
        expected_end = args.end_year if args.end_year is not None else actual[-1][0]
        summarize("captured raw_series", actual, expected_start, expected_end)
        print(f"captured values: {json.dumps([{'year': y, 'value': v} for y, v in actual], ensure_ascii=False)}")
    else:
        print("\nNo captured Network response supplied; the reported 24-year browser case was not exactly reproduced.")


if __name__ == "__main__":
    main()
