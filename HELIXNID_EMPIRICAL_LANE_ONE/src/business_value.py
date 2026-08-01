#!/usr/bin/env python3
"""HELIXNID Product 3 — convert locked empirical metrics into operational business units."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCKED_CERT = ROOT / "reports_olist_eta" / "release_certificate.json"
BATTLE = ROOT / "product_1_4" / "02_baseline_battle" / "baseline_battle_certificate.json"
OUT = ROOT / "product_1_4" / "03_business_value"
OUT.mkdir(parents=True, exist_ok=True)


def scaled_metrics(cert, volume):
    official_mae = cert["official_delivery_date_mae_days"]
    helix_mae = cert["helixnid_corrected_mae_days"]
    within1_gain = cert["helixnid_within_1_day_rate"] - cert["official_within_1_day_rate"]
    within2_gain = cert["helixnid_within_2_day_rate"] - cert["official_within_2_day_rate"]
    late_total = cert["test_late_rate"] * volume
    top10 = next(x for x in cert["risk_triage"] if x["risk_bucket"] == "top_10pct")
    flagged = 0.10 * volume
    caught = top10["late_recall"] * late_total
    return {
        "shipment_volume": volume,
        "eta_absolute_error_days_saved_per_shipment": official_mae - helix_mae,
        "eta_error_days_removed_across_volume": (official_mae - helix_mae) * volume,
        "additional_shipments_within_1_day": within1_gain * volume,
        "additional_shipments_within_2_days": within2_gain * volume,
        "expected_late_shipments_at_observed_rate": late_total,
        "high_risk_shipments_flagged_top_10pct": flagged,
        "late_shipments_captured_in_top_10pct": caught,
        "top_10pct_precision": top10["precision"],
        "top_10pct_late_recall": top10["late_recall"],
        "top_10pct_precision_lift": top10["precision_lift_vs_base_rate"],
        "median_warning_lead_hours_for_captured_late": top10["warning_lead_hours_median"],
    }


def main():
    cert = json.loads(LOCKED_CERT.read_text(encoding="utf-8"))
    volumes = [1000, 10000, 100000]
    rows = [scaled_metrics(cert, v) for v in volumes]
    with (OUT / "business_scale_table.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    battle = None
    if BATTLE.exists():
        battle = json.loads(BATTLE.read_text(encoding="utf-8"))

    v10 = rows[1]
    evidence = {
        "certificate": "HELIXNID_CARRIER_PRECISION_BUSINESS_VALUE_V1",
        "basis": "direct scaling of locked held-out empirical rates; not a revenue claim",
        "dataset_sha256": cert["orders_sha256"],
        "synthetic_rows": cert["synthetic_rows_used"],
        "per_10000_shipments": v10,
        "baseline_battle": None if battle is None else {
            "models_compared": battle["models_compared"],
            "winner": battle["winner"],
            "helixnid_rank": battle["helixnid_rank"],
        },
        "money_boundary": "No dollar savings are claimed without a buyer-specific cost-per-late-order or cost-per-promise-miss input.",
    }
    (OUT / "business_value_certificate.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")

    report = f"""# HELIXNID Carrier Precision — Business Value V1

## Per 10,000 shipments at the observed held-out rates

- ETA absolute-error days removed: **{v10['eta_error_days_removed_across_volume']:,.0f} shipment-days**
- Extra shipments moved inside ±1 day: **{v10['additional_shipments_within_1_day']:,.0f}**
- Extra shipments moved inside ±2 days: **{v10['additional_shipments_within_2_days']:,.0f}**
- Expected late shipments at observed rate: **{v10['expected_late_shipments_at_observed_rate']:,.0f}**
- Top 10% risk bucket flags: **{v10['high_risk_shipments_flagged_top_10pct']:,.0f}**
- Late shipments captured inside that bucket: **{v10['late_shipments_captured_in_top_10pct']:,.0f}**
- Late-risk concentration: **{v10['top_10pct_precision_lift']:.2f}× base rate**
- Median warning lead for captured late shipments: **{v10['median_warning_lead_hours_for_captured_late']:.1f} hours**

## Buyer-value calculator

Dollar value is kept buyer-specific:

`potential_value = caught_late_orders × buyer_value_per_early_warning`

`promise_accuracy_value = extra_within_2_day_orders × buyer_value_per_accurate_promise`

This report converts the empirical result into operational counts without inventing a financial claim.
"""
    (OUT / "BUSINESS_VALUE_REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
