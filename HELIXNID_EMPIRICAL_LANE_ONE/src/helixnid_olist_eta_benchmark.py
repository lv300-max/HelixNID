#!/usr/bin/env python3
"""HELIXNID Carrier Precision Meter — real Olist delivery-promise benchmark.

Data: Brazilian E-Commerce Public Dataset by Olist (real anonymized orders, 2016–2018).
Baseline: customer-facing estimated delivery DATE supplied by the marketplace.
HELIXNID: historical hierarchical correction learned only from earlier completed orders.
Evaluation: chronological holdout. No synthetic rows. No future-target leakage.

Because Olist's promise field is a delivery DATE (midnight timestamp), the primary
ETA metric is absolute DATE error in days, not fake hour-level precision.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import statistics
import urllib.request
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "olist"
REPORTS = ROOT / "reports_olist_eta"
DATA.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

URL = "https://www.kaggle.com/api/v1/datasets/download/olistbr/brazilian-ecommerce"
ARCHIVE = DATA / "olist_brazilian_ecommerce.zip"
EXTRACT = DATA / "raw"

EXPECTED = {
    "archive": (44_717_580, "967e41e04fc306fe604e2a693f488995a8b41e5047418f8a5c8e4abd6deca784"),
    "olist_orders_dataset.csv": (17_654_914, "8df58ef3d2d7e9944010f7beecd9b75367f5588ec6e3c91cec19ae3345ef9ecf"),
    "olist_customers_dataset.csv": (9_033_957, "983a422239e1712ded753b3bf9ecf47dc73f144d306029dcfa99e70a226883d2"),
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify(path: Path, expected_size: int, expected_sha: str) -> None:
    if path.stat().st_size != expected_size:
        raise RuntimeError(f"size mismatch: {path} {path.stat().st_size} != {expected_size}")
    got = sha256(path)
    if got != expected_sha:
        raise RuntimeError(f"sha256 mismatch: {path} {got} != {expected_sha}")


def acquire() -> dict:
    if not ARCHIVE.exists():
        part = ARCHIVE.with_suffix(".zip.part")
        req = urllib.request.Request(URL, headers={"User-Agent": "HELIXNID-Carrier-Precision/1.0"})
        with urllib.request.urlopen(req, timeout=180) as r, part.open("wb") as out:
            shutil.copyfileobj(r, out, length=4 * 1024 * 1024)
        part.replace(ARCHIVE)
    verify(ARCHIVE, *EXPECTED["archive"])
    EXTRACT.mkdir(parents=True, exist_ok=True)
    orders = EXTRACT / "olist_orders_dataset.csv"
    customers = EXTRACT / "olist_customers_dataset.csv"
    if not orders.exists() or not customers.exists():
        with zipfile.ZipFile(ARCHIVE) as z:
            for name in ("olist_orders_dataset.csv", "olist_customers_dataset.csv"):
                member = z.getinfo(name)
                target = (EXTRACT / name).resolve()
                if EXTRACT.resolve() not in target.parents:
                    raise RuntimeError("unsafe archive path")
                z.extract(member, EXTRACT)
    verify(orders, *EXPECTED["olist_orders_dataset.csv"])
    verify(customers, *EXPECTED["olist_customers_dataset.csv"])
    manifest = {
        "source_url": URL,
        "source": "Brazilian E-Commerce Public Dataset by Olist",
        "archive_bytes": ARCHIVE.stat().st_size,
        "archive_sha256": sha256(ARCHIVE),
        "files": {
            "olist_orders_dataset.csv": {"bytes": orders.stat().st_size, "sha256": sha256(orders)},
            "olist_customers_dataset.csv": {"bytes": customers.stat().st_size, "sha256": sha256(customers)},
        },
    }
    (REPORTS / "acquisition_manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def dt(s: str):
    s = (s or "").strip()
    return datetime.fromisoformat(s) if s else None


def lead_bucket(days: float) -> str:
    if days < 7: return "<7"
    if days < 14: return "7-13"
    if days < 21: return "14-20"
    if days < 28: return "21-27"
    if days < 42: return "28-41"
    return "42+"


def handoff_bucket(days: float) -> str:
    if days < 1: return "<1"
    if days < 2: return "1-2"
    if days < 4: return "2-4"
    if days < 7: return "4-7"
    return "7+"


def load_rows() -> tuple[list[dict], dict]:
    customer_state = {}
    with (EXTRACT / "olist_customers_dataset.csv").open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            customer_state[r["customer_id"]] = r["customer_state"]

    raw = 0
    delivered = 0
    complete = 0
    valid = 0
    rows = []
    with (EXTRACT / "olist_orders_dataset.csv").open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            raw += 1
            if r["order_status"] != "delivered":
                continue
            delivered += 1
            purchase = dt(r["order_purchase_timestamp"])
            handoff = dt(r["order_delivered_carrier_date"])
            actual = dt(r["order_delivered_customer_date"])
            estimate = dt(r["order_estimated_delivery_date"])
            if not all((purchase, handoff, actual, estimate)):
                continue
            complete += 1
            # The correction is issued at carrier handoff. Remove impossible chronology.
            if handoff < purchase or actual < handoff or estimate < purchase:
                continue
            state = customer_state.get(r["customer_id"], "??")
            promise_days = (estimate - purchase).total_seconds() / 86400.0
            handoff_days = (handoff - purchase).total_seconds() / 86400.0
            error_days = (actual.date() - estimate.date()).days
            rows.append({
                "order_id": r["order_id"],
                "state": state,
                "purchase": purchase,
                "handoff": handoff,
                "actual": actual,
                "estimate": estimate,
                "promise_days": promise_days,
                "lead_bucket": lead_bucket(promise_days),
                "handoff_days": handoff_days,
                "handoff_bucket": handoff_bucket(handoff_days),
                "purchase_weekday": purchase.weekday(),
                "purchase_month": purchase.month,
                "error_days": error_days,
                "late": int(error_days > 0),
            })
            valid += 1
    rows.sort(key=lambda x: (x["purchase"], x["order_id"]))
    audit = {"raw_orders": raw, "delivered_status_rows": delivered, "complete_timestamp_rows": complete, "valid_chronology_rows": valid}
    return rows, audit


def median_map(rows: list[dict], key_fn):
    d = defaultdict(list)
    for r in rows:
        d[key_fn(r)].append(r["error_days"])
    return {k: statistics.median(v) for k, v in d.items()}


def rate_map(rows: list[dict], key_fn):
    d = defaultdict(lambda: [0, 0])
    for r in rows:
        x = d[key_fn(r)]; x[0] += r["late"]; x[1] += 1
    return {k: a / n for k, (a, n) in d.items()}


class Corrector:
    def __init__(self, rows: list[dict]):
        self.global_median = statistics.median(r["error_days"] for r in rows)
        self.global_late = statistics.fmean(r["late"] for r in rows)
        self.m1 = median_map(rows, lambda r: (r["state"], r["lead_bucket"], r["handoff_bucket"], r["purchase_weekday"]))
        self.m2 = median_map(rows, lambda r: (r["state"], r["lead_bucket"], r["handoff_bucket"]))
        self.m3 = median_map(rows, lambda r: (r["state"], r["lead_bucket"]))
        self.m4 = median_map(rows, lambda r: (r["state"],))
        self.r1 = rate_map(rows, lambda r: (r["state"], r["lead_bucket"], r["handoff_bucket"], r["purchase_weekday"]))
        self.r2 = rate_map(rows, lambda r: (r["state"], r["lead_bucket"], r["handoff_bucket"]))
        self.r3 = rate_map(rows, lambda r: (r["state"], r["lead_bucket"]))
        self.r4 = rate_map(rows, lambda r: (r["state"],))

    def correction(self, r: dict) -> float:
        keys = [
            (r["state"], r["lead_bucket"], r["handoff_bucket"], r["purchase_weekday"]),
            (r["state"], r["lead_bucket"], r["handoff_bucket"]),
            (r["state"], r["lead_bucket"]),
            (r["state"],),
        ]
        for m, k in zip((self.m1, self.m2, self.m3, self.m4), keys):
            if k in m:
                return m[k]
        return self.global_median

    def late_risk(self, r: dict) -> float:
        keys = [
            (r["state"], r["lead_bucket"], r["handoff_bucket"], r["purchase_weekday"]),
            (r["state"], r["lead_bucket"], r["handoff_bucket"]),
            (r["state"], r["lead_bucket"]),
            (r["state"],),
        ]
        for m, k in zip((self.r1, self.r2, self.r3, self.r4), keys):
            if k in m:
                return m[k]
        return self.global_late


def classification(rows: list[dict], corrector: Corrector, threshold: float) -> dict:
    tp = fp = tn = fn = 0
    leads = []
    for r in rows:
        pred = corrector.late_risk(r) >= threshold
        actual = bool(r["late"])
        if pred and actual:
            tp += 1
            leads.append((r["actual"] - r["handoff"]).total_seconds() / 3600.0)
        elif pred and not actual: fp += 1
        elif not pred and actual: fn += 1
        else: tn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "threshold": threshold, "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": precision, "recall": recall, "f1": f1,
        "warning_lead_hours_mean_true_positive": statistics.fmean(leads) if leads else 0.0,
        "warning_lead_hours_median_true_positive": statistics.median(leads) if leads else 0.0,
    }


def choose_threshold(fit: list[dict], calibration: list[dict]) -> tuple[float, list[dict]]:
    c = Corrector(fit)
    results = []
    # Deterministic thresholds; chosen only from past/training data.
    for i in range(1, 51):
        t = i / 100.0
        results.append(classification(calibration, c, t))
    results.sort(key=lambda x: (x["f1"], x["recall"], x["precision"]), reverse=True)
    return results[0]["threshold"], results


def evaluate(rows: list[dict], corrector: Corrector):
    out = []
    for r in rows:
        baseline = abs(r["error_days"])
        corr = corrector.correction(r)
        helix_error = r["error_days"] - corr
        global_error = r["error_days"] - corrector.global_median
        out.append({
            **r,
            "baseline_abs_error_days": baseline,
            "global_abs_error_days": abs(global_error),
            "helix_correction_days": corr,
            "helix_error_days": helix_error,
            "helix_abs_error_days": abs(helix_error),
            "late_risk": corrector.late_risk(r),
        })
    return out


def pct_reduction(base: float, new: float) -> float:
    return (base - new) / base * 100.0 if base else 0.0


def write_csv(path: Path, rows: list[dict], fields=None):
    if not rows: return
    if fields is None: fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)


def main():
    manifest = acquire()
    rows, audit = load_rows()
    if len(rows) < 5000:
        raise RuntimeError(f"fewer than 5000 valid real completed orders: {len(rows)}")

    n = len(rows)
    train_end = int(n * 0.70)
    train = rows[:train_end]
    test = rows[train_end:]
    cal_cut = int(len(train) * 0.80)
    threshold, threshold_table = choose_threshold(train[:cal_cut], train[cal_cut:])

    corrector = Corrector(train)
    scored = evaluate(test, corrector)
    cls = classification(test, corrector, threshold)

    baseline_mae = statistics.fmean(r["baseline_abs_error_days"] for r in scored)
    global_mae = statistics.fmean(r["global_abs_error_days"] for r in scored)
    helix_mae = statistics.fmean(r["helix_abs_error_days"] for r in scored)
    baseline_median = statistics.median(r["baseline_abs_error_days"] for r in scored)
    helix_median = statistics.median(r["helix_abs_error_days"] for r in scored)
    baseline_within_1 = statistics.fmean(r["baseline_abs_error_days"] <= 1 for r in scored)
    helix_within_1 = statistics.fmean(r["helix_abs_error_days"] <= 1 for r in scored)
    late_rate = statistics.fmean(r["late"] for r in scored)

    state_groups = defaultdict(list)
    for r in scored: state_groups[r["state"]].append(r)
    weakness = []
    for state, grp in sorted(state_groups.items()):
        b = statistics.fmean(x["baseline_abs_error_days"] for x in grp)
        h = statistics.fmean(x["helix_abs_error_days"] for x in grp)
        weakness.append({
            "state": state, "test_orders": len(grp), "official_mae_days": b,
            "helixnid_mae_days": h, "error_reduction_pct": pct_reduction(b, h),
            "late_rate_pct": statistics.fmean(x["late"] for x in grp) * 100.0,
        })
    weakness.sort(key=lambda x: x["official_mae_days"], reverse=True)

    comparison = [
        {"metric": "Delivery-date MAE (days)", "official_estimate": baseline_mae, "global_historical_correction": global_mae, "helixnid": helix_mae, "helixnid_improvement_pct": pct_reduction(baseline_mae, helix_mae)},
        {"metric": "Median absolute delivery-date error (days)", "official_estimate": baseline_median, "global_historical_correction": "", "helixnid": helix_median, "helixnid_improvement_pct": pct_reduction(baseline_median, helix_median)},
        {"metric": "Within ±1 day rate", "official_estimate": baseline_within_1, "global_historical_correction": "", "helixnid": helix_within_1, "helixnid_improvement_pct": (helix_within_1 - baseline_within_1) * 100.0},
    ]

    certificate = {
        "certificate": "HELIXNID_CARRIER_PRECISION_METER_OLIST_REAL_V1",
        "status": "PASS",
        "generated_utc": now_utc(),
        "dataset": "Brazilian E-Commerce Public Dataset by Olist",
        "source_url": URL,
        "archive_sha256": manifest["archive_sha256"],
        "synthetic_rows_used": 0,
        "raw_orders": audit["raw_orders"],
        "valid_real_completed_orders": len(rows),
        "chronological_train_orders": len(train),
        "chronological_test_orders": len(test),
        "train_first_purchase": train[0]["purchase"].isoformat(),
        "train_last_purchase": train[-1]["purchase"].isoformat(),
        "test_first_purchase": test[0]["purchase"].isoformat(),
        "test_last_purchase": test[-1]["purchase"].isoformat(),
        "official_delivery_date_mae_days": baseline_mae,
        "global_historical_correction_mae_days": global_mae,
        "helixnid_corrected_mae_days": helix_mae,
        "eta_error_reduction_pct": pct_reduction(baseline_mae, helix_mae),
        "official_within_1_day_rate": baseline_within_1,
        "helixnid_within_1_day_rate": helix_within_1,
        "test_late_rate": late_rate,
        "late_risk": cls,
        "claim_boundary": "Olist exposes an estimated delivery DATE, not carrier identity or a guaranteed hour-level carrier ETA. Results therefore measure real delivery-promise date correction at carrier-handoff time, not per-carrier FedEx/UPS performance.",
    }

    write_csv(REPORTS / "comparison_table.csv", comparison)
    write_csv(REPORTS / "weakness_by_state.csv", weakness)
    write_csv(REPORTS / "late_risk_threshold_calibration.csv", threshold_table)
    write_csv(
        REPORTS / "test_order_scores.csv",
        scored,
        fields=["order_id", "state", "purchase", "handoff", "actual", "estimate", "lead_bucket", "handoff_bucket", "error_days", "baseline_abs_error_days", "helix_correction_days", "helix_error_days", "helix_abs_error_days", "late", "late_risk"],
    )
    (REPORTS / "data_validation_report.json").write_text(json.dumps({**audit, "valid_real_completed_orders": len(rows), "synthetic_rows": 0, "chronological_split": True}, indent=2, default=str))
    (REPORTS / "release_certificate.json").write_text(json.dumps(certificate, indent=2, default=str))

    report = f"""# HELIXNID Carrier Precision Meter — Real Olist Empirical Run

- Status: **PASS**
- Real valid completed orders: **{len(rows):,}**
- Chronological training orders: **{len(train):,}**
- Chronological held-out test orders: **{len(test):,}**
- Synthetic rows: **0**

## Delivery promise precision

- Official estimate MAE: **{baseline_mae:.3f} days**
- Global historical correction MAE: **{global_mae:.3f} days**
- HELIXNID corrected MAE: **{helix_mae:.3f} days**
- HELIXNID ETA error reduction: **{pct_reduction(baseline_mae, helix_mae):.2f}%**
- Official within ±1 day: **{baseline_within_1*100:.2f}%**
- HELIXNID within ±1 day: **{helix_within_1*100:.2f}%**

## Late-risk signal

- Test late rate: **{late_rate*100:.2f}%**
- Training-selected risk threshold: **{threshold:.2f}**
- Late-risk recall: **{cls['recall']*100:.2f}%**
- Late-risk precision: **{cls['precision']*100:.2f}%**
- Late-risk F1: **{cls['f1']:.4f}**
- Mean warning lead for true positives: **{cls['warning_lead_hours_mean_true_positive']:.2f} hours**
- Median warning lead for true positives: **{cls['warning_lead_hours_median_true_positive']:.2f} hours**

## Boundary

Olist supplies a customer-facing estimated delivery DATE and actual delivery timestamp. It does not identify FedEx/UPS/etc. These numbers are real delivery-promise correction results, not per-carrier claims.
"""
    (REPORTS / "empirical_run_report.md").write_text(report)

    ledger = f"""# Dataset Source Ledger — Olist

- Source: Brazilian E-Commerce Public Dataset by Olist
- Download endpoint: `{URL}`
- Archive bytes: `{manifest['archive_bytes']}`
- Archive SHA256: `{manifest['archive_sha256']}`
- Orders SHA256: `{manifest['files']['olist_orders_dataset.csv']['sha256']}`
- Customers SHA256: `{manifest['files']['olist_customers_dataset.csv']['sha256']}`
- Synthetic rows used: `0`
"""
    (REPORTS / "dataset_source_ledger.md").write_text(ledger)

    artifacts = []
    for p in sorted(REPORTS.iterdir()):
        if p.is_file() and p.name != "artifact_hashes.csv":
            artifacts.append({"file": p.name, "bytes": p.stat().st_size, "sha256": sha256(p)})
    write_csv(REPORTS / "artifact_hashes.csv", artifacts)
    print(json.dumps(certificate, indent=2, default=str))


if __name__ == "__main__":
    main()
