#!/usr/bin/env python3
"""HELIXNID Product 1 — robustness attack on the locked real Olist lane."""
from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from datetime import timezone
from pathlib import Path

import helixnid_olist_eta_benchmark as core

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "product_1_4" / "01_robustness"
OUT.mkdir(parents=True, exist_ok=True)


def mae(values):
    return statistics.fmean(values) if values else float("nan")


def evaluate(train, test, label, family, detail=""):
    if len(train) < 500 or len(test) < 100:
        return None
    model = core.HistoricalCorrector(train)
    base = [abs(r["error_days"]) for r in test]
    helix = [abs(r["error_days"] - model.correction_days(r)) for r in test]
    b = mae(base); h = mae(helix)
    return {
        "family": family,
        "test": label,
        "detail": detail,
        "train_rows": len(train),
        "test_rows": len(test),
        "official_mae_days": b,
        "helixnid_mae_days": h,
        "error_reduction_pct": ((b-h)/b*100.0) if b else 0.0,
        "official_median_abs_error_days": statistics.median(base),
        "helixnid_median_abs_error_days": statistics.median(helix),
        "official_within_1_day": statistics.fmean(x <= 1 for x in base),
        "helixnid_within_1_day": statistics.fmean(x <= 1 for x in helix),
        "official_within_2_days": statistics.fmean(x <= 2 for x in base),
        "helixnid_within_2_days": statistics.fmean(x <= 2 for x in helix),
    }


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


def main():
    manifest = core.acquire_orders()
    rows, audit = core.load_real_orders()
    tests = []

    # A. Fixed chronological splits.
    for frac in (0.50, 0.60, 0.70, 0.80):
        cut = int(len(rows) * frac)
        result = evaluate(rows[:cut], rows[cut:], f"chronological_{int(frac*100)}_{int((1-frac)*100)}", "chronological_split")
        if result: tests.append(result)

    # B. Rolling-origin future blocks. Each fold trains only on rows before the block.
    boundaries = (0.40, 0.50, 0.60, 0.70, 0.80, 0.90)
    for a, b in zip(boundaries[:-1], boundaries[1:]):
        train_end = int(len(rows) * a)
        test_end = int(len(rows) * b)
        result = evaluate(rows[:train_end], rows[train_end:test_end], f"rolling_{int(a*100)}_to_{int(b*100)}", "rolling_origin")
        if result: tests.append(result)

    # C. Calendar-month future holdouts for the final eight sufficiently large months.
    month_rows = defaultdict(list)
    for r in rows:
        month_rows[r["purchase"].strftime("%Y-%m")].append(r)
    months = sorted(m for m, vals in month_rows.items() if len(vals) >= 500)[-8:]
    for month in months:
        test = month_rows[month]
        start = min(r["purchase"] for r in test)
        train = [r for r in rows if r["purchase"] < start]
        result = evaluate(train, test, f"month_{month}", "calendar_holdout")
        if result: tests.append(result)

    # D. Stress segments evaluated inside the locked 70/30 future test.
    cut = int(len(rows) * 0.70)
    train, future = rows[:cut], rows[cut:]
    fitted = core.HistoricalCorrector(train)
    segment_defs = {
        "late_only": lambda r: r["error_days"] > 0,
        "on_or_early_only": lambda r: r["error_days"] <= 0,
        "handoff_7plus": lambda r: r["handoff_bucket"] == "7+",
        "promise_under_14d": lambda r: r["lead_bucket"] in {"<7", "7-13"},
        "promise_28plus": lambda r: r["lead_bucket"] in {"28-41", "42+"},
        "negative_slack": lambda r: r["slack_bucket"] == "<0",
    }
    for name, pred in segment_defs.items():
        test = [r for r in future if pred(r)]
        if len(test) < 100: continue
        base = [abs(r["error_days"]) for r in test]
        helix = [abs(r["error_days"] - fitted.correction_days(r)) for r in test]
        b = mae(base); h = mae(helix)
        tests.append({
            "family": "stress_segment", "test": name, "detail": "locked_70_30_model",
            "train_rows": len(train), "test_rows": len(test),
            "official_mae_days": b, "helixnid_mae_days": h,
            "error_reduction_pct": ((b-h)/b*100.0) if b else 0.0,
            "official_median_abs_error_days": statistics.median(base),
            "helixnid_median_abs_error_days": statistics.median(helix),
            "official_within_1_day": statistics.fmean(x <= 1 for x in base),
            "helixnid_within_1_day": statistics.fmean(x <= 1 for x in helix),
            "official_within_2_days": statistics.fmean(x <= 2 for x in base),
            "helixnid_within_2_days": statistics.fmean(x <= 2 for x in helix),
        })

    reductions = [r["error_reduction_pct"] for r in tests]
    overall_tests = [r for r in tests if r["family"] != "stress_segment"]
    overall_reductions = [r["error_reduction_pct"] for r in overall_tests]
    certificate = {
        "certificate": "HELIXNID_CARRIER_PRECISION_ROBUSTNESS_V1",
        "status": "PASS" if tests and min(overall_reductions) > 0 else "REVIEW",
        "dataset_sha256": manifest["orders_sha256"],
        "synthetic_rows": 0,
        "valid_real_completed_orders": audit["valid_real_completed_orders"],
        "tests_run": len(tests),
        "non_segment_tests": len(overall_tests),
        "minimum_non_segment_error_reduction_pct": min(overall_reductions),
        "median_non_segment_error_reduction_pct": statistics.median(overall_reductions),
        "maximum_non_segment_error_reduction_pct": max(overall_reductions),
        "minimum_all_tests_error_reduction_pct": min(reductions),
        "tests": tests,
    }
    write_csv(OUT / "robustness_results.csv", tests)
    (OUT / "robustness_certificate.json").write_text(json.dumps(certificate, indent=2), encoding="utf-8")
    report = [
        "# HELIXNID Robustness Attack V1", "",
        f"- Real completed orders: **{audit['valid_real_completed_orders']:,}**",
        f"- Tests: **{len(tests)}**",
        f"- Lowest non-segment ETA error reduction: **{min(overall_reductions):.2f}%**",
        f"- Median non-segment ETA error reduction: **{statistics.median(overall_reductions):.2f}%**",
        f"- Highest non-segment ETA error reduction: **{max(overall_reductions):.2f}%**",
        "", "Every chronological and rolling test trains only on earlier orders.",
    ]
    (OUT / "ROBUSTNESS_REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({k:v for k,v in certificate.items() if k != "tests"}, indent=2))


if __name__ == "__main__":
    main()
