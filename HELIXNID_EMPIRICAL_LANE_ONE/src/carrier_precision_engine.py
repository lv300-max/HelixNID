#!/usr/bin/env python3
"""HELIXNID Product 4 — deployable Carrier Precision scoring engine.

Trains a final JSON artifact from the validated real Olist history and scores new
shipment promises at carrier handoff. Carrier/service fields are accepted and
returned, but Olist has no carrier-brand identity, so V1 does not learn a brand effect.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import helixnid_olist_eta_benchmark as core

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "product_1_4" / "04_scoring_engine"
OUT.mkdir(parents=True, exist_ok=True)
MODEL_PATH = OUT / "carrier_precision_model_v1.json"
LOCKED_CERT = ROOT / "reports_olist_eta" / "release_certificate.json"


def _group(rows, cols, value, minimum, mean=False):
    d = defaultdict(list)
    for r in rows:
        d[tuple(r[c] for c in cols)].append(r[value])
    out = []
    for key, vals in sorted(d.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        if len(vals) >= minimum:
            out.append({
                "key": list(key),
                "value": statistics.fmean(vals) if mean else statistics.median(vals),
                "count": len(vals),
            })
    return out


def build_model():
    manifest = core.acquire_orders()
    rows, audit = core.load_real_orders()
    locked = json.loads(LOCKED_CERT.read_text(encoding="utf-8")) if LOCKED_CERT.exists() else None
    levels = []
    for cols, minimum in core.LEVELS:
        levels.append({
            "columns": list(cols),
            "minimum_count": minimum,
            "correction": _group(rows, cols, "error_days", minimum, mean=False),
            "late_risk": _group(rows, cols, "late", minimum, mean=True),
        })
    artifact = {
        "model": "HELIXNID_CARRIER_PRECISION_MODEL_V1",
        "built_utc": datetime.now(timezone.utc).isoformat(),
        "training_source": "Brazilian E-Commerce Public Dataset by Olist",
        "dataset_sha256": manifest["orders_sha256"],
        "trained_real_completed_orders": audit["valid_real_completed_orders"],
        "synthetic_rows": 0,
        "validated_holdout_certificate": None if locked is None else locked.get("certificate"),
        "validated_eta_error_reduction_pct": None if locked is None else locked.get("eta_error_reduction_pct"),
        "target": "delivery-date error in days at carrier handoff",
        "global_correction_days": statistics.median(r["error_days"] for r in rows),
        "global_late_risk": statistics.fmean(r["late"] for r in rows),
        "levels": levels,
        "scope_boundary": "V1 Olist training data does not identify FedEx/UPS/DHL carrier brands; carrier and service are passthrough fields until carrier-labelled evidence is acquired.",
    }
    MODEL_PATH.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return artifact


def _parse(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _features(payload):
    purchase = _parse(payload.get("purchase_time") or payload.get("ship_time"))
    handoff = _parse(payload["carrier_handoff_time"])
    eta = _parse(payload.get("carrier_eta_time") or payload.get("promised_delivery_time"))
    if handoff < purchase:
        raise ValueError("carrier_handoff_time cannot be before purchase/ship time")
    return {
        "purchase": purchase,
        "handoff": handoff,
        "eta": eta,
        "lead_bucket": core.lead_bucket((eta-purchase).total_seconds()/86400.0),
        "handoff_bucket": core.handoff_bucket((handoff-purchase).total_seconds()/86400.0),
        "slack_bucket": core.slack_bucket((eta-handoff).total_seconds()/86400.0),
        "weekday": purchase.weekday(),
    }


def _compile_level(level, table_name):
    return {tuple(str(x) for x in item["key"]): item for item in level[table_name]}


def _lookup(features, artifact, table_name, fallback):
    for i, level in enumerate(artifact["levels"]):
        key = tuple(str(features[c]) for c in level["columns"])
        item = _compile_level(level, table_name).get(key)
        if item is not None:
            return float(item["value"]), int(item["count"]), i, level["columns"]
    return float(fallback), artifact["trained_real_completed_orders"], None, ["global"]


def score(payload, artifact=None):
    artifact = artifact or json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    f = _features(payload)
    correction, correction_count, level, columns = _lookup(f, artifact, "correction", artifact["global_correction_days"])
    risk, risk_count, _, _ = _lookup(f, artifact, "late_risk", artifact["global_late_risk"])
    corrected = f["eta"] + timedelta(days=correction)
    if level == 0 and min(correction_count, risk_count) >= 100:
        confidence = "HIGH"
    elif level is not None:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"
    if risk >= 0.20:
        risk_band = "HIGH"
    elif risk >= 0.10:
        risk_band = "ELEVATED"
    elif risk >= 0.05:
        risk_band = "WATCH"
    else:
        risk_band = "LOW"
    return {
        "shipment_id": payload.get("shipment_id"),
        "carrier": payload.get("carrier"),
        "service": payload.get("service"),
        "destination": payload.get("destination") or payload.get("destination_zip"),
        "original_eta": f["eta"].isoformat(),
        "helixnid_corrected_eta": corrected.isoformat(),
        "helixnid_correction_days": correction,
        "late_probability": risk,
        "late_risk_band": risk_band,
        "confidence": confidence,
        "matched_history_rows": min(correction_count, risk_count),
        "matched_level": columns,
        "warning_window_hours_to_original_eta": (f["eta"]-f["handoff"]).total_seconds()/3600.0,
        "model": artifact["model"],
        "dataset_sha256": artifact["dataset_sha256"],
    }


def score_csv(input_path, output_path):
    artifact = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    with Path(input_path).open(newline="", encoding="utf-8") as f:
        rows = [score(r, artifact) for r in csv.DictReader(f)]
    if rows:
        with Path(output_path).open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    return rows


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("train")
    one = sub.add_parser("score")
    one.add_argument("--json", required=True, help="JSON shipment payload")
    batch = sub.add_parser("batch")
    batch.add_argument("--input", required=True)
    batch.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.cmd == "train":
        a = build_model(); print(json.dumps({k:v for k,v in a.items() if k != "levels"}, indent=2))
    elif args.cmd == "score":
        if not MODEL_PATH.exists(): build_model()
        print(json.dumps(score(json.loads(args.json)), indent=2))
    else:
        if not MODEL_PATH.exists(): build_model()
        rows = score_csv(args.input, args.output); print(json.dumps({"scored_rows": len(rows), "output": args.output}, indent=2))


if __name__ == "__main__":
    main()
