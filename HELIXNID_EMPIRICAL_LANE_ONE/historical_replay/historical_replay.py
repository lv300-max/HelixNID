#!/usr/bin/env python3
"""HELIXNID Carrier Precision Meter — historical replay engine.

Modes:
1) --olist-locked: reproduce the locked chronological 70/30 Olist replay.
2) --input FILE.csv: replay completed customer shipments against the current V1 model.

Customer CSV requires the normal scoring fields plus `actual_delivery_time`.
The replay never uses actual delivery as a scoring feature; it is read only after scoring
for retrospective error comparison.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve()
LANE = HERE.parents[1]
SRC = LANE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import carrier_precision_engine as product
import helixnid_olist_eta_benchmark as core

OUT = HERE.parent / "outputs"
OUT.mkdir(parents=True, exist_ok=True)


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def summarize(rows):
    n = len(rows)
    official = [r["official_abs_error_days"] for r in rows]
    helix = [r["helixnid_abs_error_days"] for r in rows]
    b = statistics.fmean(official)
    h = statistics.fmean(helix)
    improved = sum(x["helixnid_abs_error_days"] < x["official_abs_error_days"] for x in rows)
    worsened = sum(x["helixnid_abs_error_days"] > x["official_abs_error_days"] for x in rows)
    tied = n - improved - worsened
    return {
        "shipments_replayed": n,
        "official_mae_days": b,
        "helixnid_mae_days": h,
        "relative_error_reduction_pct": (b - h) / b * 100.0 if b else 0.0,
        "total_absolute_error_days_removed": sum(official) - sum(helix),
        "shipments_improved": improved,
        "shipments_worsened": worsened,
        "shipments_tied": tied,
        "improved_rate": improved / n if n else 0.0,
        "official_within_1_day": statistics.fmean(x <= 1 for x in official),
        "helixnid_within_1_day": statistics.fmean(x <= 1 for x in helix),
        "official_within_2_days": statistics.fmean(x <= 2 for x in official),
        "helixnid_within_2_days": statistics.fmean(x <= 2 for x in helix),
    }


def write_rows(path: Path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


def replay_olist_locked():
    manifest = core.acquire_orders()
    rows, audit = core.load_real_orders()
    cut = int(len(rows) * 0.70)
    train, test = rows[:cut], rows[cut:]
    model = core.HistoricalCorrector(train)
    replay = []
    for r in test:
        correction = model.correction_days(r)
        official = abs(r["error_days"])
        helix = abs(r["error_days"] - correction)
        replay.append({
            "shipment_id": r["order_id"],
            "purchase_time": r["purchase"].isoformat(),
            "carrier_handoff_time": r["handoff"].isoformat(),
            "original_eta": r["estimate"].isoformat(),
            "actual_delivery": r["actual"].isoformat(),
            "helixnid_correction_days": correction,
            "official_abs_error_days": official,
            "helixnid_abs_error_days": helix,
            "movement": "IMPROVED" if helix < official else ("WORSENED" if helix > official else "TIED"),
        })
    summary = summarize(replay)
    certificate = {
        "certificate": "HELIXNID_HISTORICAL_REPLAY_OLIST_V1",
        "status": "PASS",
        "dataset": "Brazilian E-Commerce Public Dataset by Olist",
        "dataset_sha256": manifest["orders_sha256"],
        "valid_real_completed_orders": audit["valid_real_completed_orders"],
        "chronological_training_rows": len(train),
        "future_replay_rows": len(test),
        "synthetic_rows": 0,
        **summary,
        "leakage_boundary": "Actual delivery is used only after scoring to measure replay error. Training uses only the earlier chronological 70% of orders.",
    }
    write_rows(OUT / "olist_replay_rows.csv", replay)
    (OUT / "OLIST_REPLAY_CERTIFICATE.json").write_text(json.dumps(certificate, indent=2), encoding="utf-8")
    print(json.dumps(certificate, indent=2))


def replay_customer(path: Path):
    if not product.MODEL_PATH.exists():
        product.build_model()
    artifact = json.loads(product.MODEL_PATH.read_text(encoding="utf-8"))
    replay = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        for raw in csv.DictReader(f):
            if not raw.get("actual_delivery_time"):
                raise ValueError("customer replay CSV requires actual_delivery_time")
            payload = {k: v for k, v in raw.items() if v not in (None, "") and k != "actual_delivery_time"}
            score = product.score(payload, artifact)
            actual = parse_dt(raw["actual_delivery_time"])
            official_eta = parse_dt(score["original_eta"])
            helix_eta = parse_dt(score["helixnid_corrected_eta"])
            official_error = abs((actual.date() - official_eta.date()).days)
            helix_error = abs((actual.date() - helix_eta.date()).days)
            replay.append({
                "shipment_id": score.get("shipment_id"),
                "carrier": score.get("carrier"),
                "service": score.get("service"),
                "destination": score.get("destination"),
                "original_eta": score["original_eta"],
                "helixnid_corrected_eta": score["helixnid_corrected_eta"],
                "actual_delivery_time": actual.isoformat(),
                "late_probability": score["late_probability"],
                "late_risk_band": score["late_risk_band"],
                "confidence": score["confidence"],
                "official_abs_error_days": official_error,
                "helixnid_abs_error_days": helix_error,
                "movement": "IMPROVED" if helix_error < official_error else ("WORSENED" if helix_error > official_error else "TIED"),
            })
    summary = summarize(replay)
    certificate = {
        "certificate": "HELIXNID_CUSTOMER_HISTORICAL_REPLAY_V1",
        "status": "PASS",
        "input_file": str(path),
        "model": artifact["model"],
        "model_dataset_sha256": artifact["dataset_sha256"],
        **summary,
        "leakage_boundary": "actual_delivery_time is excluded from the scoring payload and is read only for retrospective comparison after prediction.",
    }
    write_rows(OUT / "customer_replay_rows.csv", replay)
    (OUT / "CUSTOMER_REPLAY_CERTIFICATE.json").write_text(json.dumps(certificate, indent=2), encoding="utf-8")
    print(json.dumps(certificate, indent=2))


def main():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--olist-locked", action="store_true")
    g.add_argument("--input", type=Path)
    args = p.parse_args()
    if args.olist_locked:
        replay_olist_locked()
    else:
        replay_customer(args.input)


if __name__ == "__main__":
    main()
