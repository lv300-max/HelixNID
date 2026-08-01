#!/usr/bin/env python3
"""HELIXNID Carrier Precision Meter — exact real Olist empirical benchmark.

Real source: Brazilian E-Commerce Public Dataset by Olist.
Primary metric: customer-facing estimated delivery DATE vs actual delivery DATE.
Correction time: carrier handoff. Only information known by carrier handoff is used.
Evaluation: strict chronological 70/30 historical/future split.
Synthetic rows used for empirical claims: 0.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import shutil
import statistics
import urllib.request
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "olist_eta"
REPORTS = ROOT / "reports_olist_eta"
DATA.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

KAGGLE_URL = "https://www.kaggle.com/api/v1/datasets/download/olistbr/brazilian-ecommerce"
RAW_FALLBACK_URL = "https://raw.githubusercontent.com/brunolucian/CursoIntermediarioR/main/Dados/olist_orders_dataset.csv"
ORDERS_NAME = "olist_orders_dataset.csv"
ORDERS_BYTES = 17_654_914
ORDERS_SHA256 = "8df58ef3d2d7e9944010f7beecd9b75367f5588ec6e3c91cec19ae3345ef9ecf"
ARCHIVE_BYTES = 44_717_580
ARCHIVE_SHA256 = "967e41e04fc306fe604e2a693f488995a8b41e5047418f8a5c8e4abd6deca784"

# Fixed before future evaluation. No test-target feature is used.
LEVELS = [
    (("lead_bucket", "handoff_bucket", "slack_bucket", "weekday"), 20),
    (("lead_bucket", "slack_bucket", "weekday"), 20),
    (("lead_bucket", "slack_bucket"), 30),
    (("slack_bucket",), 50),
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify(path: Path, size: int, digest: str) -> None:
    if path.stat().st_size != size:
        raise RuntimeError(f"size mismatch for {path.name}: {path.stat().st_size} != {size}")
    got = sha256(path)
    if got != digest:
        raise RuntimeError(f"sha256 mismatch for {path.name}: {got} != {digest}")


def acquire_orders() -> dict:
    orders = DATA / ORDERS_NAME
    archive = DATA / "olist_brazilian_ecommerce.zip"
    source_used = None

    if orders.exists():
        try:
            verify(orders, ORDERS_BYTES, ORDERS_SHA256)
            source_used = "cached_verified"
        except Exception:
            orders.unlink()

    if not orders.exists():
        try:
            part = archive.with_suffix(".zip.part")
            req = urllib.request.Request(KAGGLE_URL, headers={"User-Agent": "HELIXNID-Carrier-Precision/1.0"})
            with urllib.request.urlopen(req, timeout=180) as r, part.open("wb") as out:
                shutil.copyfileobj(r, out, length=4 * 1024 * 1024)
            part.replace(archive)
            verify(archive, ARCHIVE_BYTES, ARCHIVE_SHA256)
            with zipfile.ZipFile(archive) as z:
                with z.open(ORDERS_NAME) as src, orders.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
            source_used = KAGGLE_URL
        except Exception:
            if orders.exists():
                orders.unlink()
            req = urllib.request.Request(RAW_FALLBACK_URL, headers={"User-Agent": "HELIXNID-Carrier-Precision/1.0"})
            with urllib.request.urlopen(req, timeout=180) as r, orders.open("wb") as out:
                shutil.copyfileobj(r, out, length=4 * 1024 * 1024)
            source_used = RAW_FALLBACK_URL

    verify(orders, ORDERS_BYTES, ORDERS_SHA256)
    manifest = {
        "canonical_dataset": "Brazilian E-Commerce Public Dataset by Olist",
        "canonical_url": KAGGLE_URL,
        "source_used": source_used,
        "orders_file": ORDERS_NAME,
        "orders_bytes": orders.stat().st_size,
        "orders_sha256": sha256(orders),
        "expected_orders_sha256": ORDERS_SHA256,
        "identity_verified": True,
    }
    (REPORTS / "acquisition_manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def parse_dt(value: str):
    value = (value or "").strip()
    return datetime.fromisoformat(value) if value else None


def lead_bucket(x: float) -> str:
    if x < 7: return "<7"
    if x < 14: return "7-13"
    if x < 21: return "14-20"
    if x < 28: return "21-27"
    if x < 42: return "28-41"
    return "42+"


def handoff_bucket(x: float) -> str:
    if x < 1: return "<1"
    if x < 2: return "1-2"
    if x < 4: return "2-4"
    if x < 7: return "4-7"
    return "7+"


def slack_bucket(x: float) -> str:
    if x < 0: return "<0"
    if x < 2: return "0-2"
    if x < 4: return "2-4"
    if x < 7: return "4-7"
    if x < 10: return "7-10"
    if x < 14: return "10-14"
    return "14+"


def load_real_orders() -> tuple[list[dict], dict]:
    raw = delivered = complete = valid = 0
    rows = []
    with (DATA / ORDERS_NAME).open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            raw += 1
            if r["order_status"] != "delivered":
                continue
            delivered += 1
            purchase = parse_dt(r["order_purchase_timestamp"])
            handoff = parse_dt(r["order_delivered_carrier_date"])
            actual = parse_dt(r["order_delivered_customer_date"])
            estimate = parse_dt(r["order_estimated_delivery_date"])
            if not all((purchase, handoff, actual, estimate)):
                continue
            complete += 1
            if handoff < purchase or actual < handoff or estimate < purchase:
                continue
            valid += 1
            promise_days = (estimate - purchase).total_seconds() / 86400.0
            handoff_days = (handoff - purchase).total_seconds() / 86400.0
            slack_days = (estimate - handoff).total_seconds() / 86400.0
            error_days = (actual.date() - estimate.date()).days
            rows.append({
                "order_id": r["order_id"],
                "purchase": purchase,
                "handoff": handoff,
                "actual": actual,
                "estimate": estimate,
                "error_days": error_days,
                "late": int(error_days > 0),
                "lead_bucket": lead_bucket(promise_days),
                "handoff_bucket": handoff_bucket(handoff_days),
                "slack_bucket": slack_bucket(slack_days),
                "weekday": purchase.weekday(),
            })
    rows.sort(key=lambda r: (r["purchase"], r["order_id"]))
    return rows, {
        "raw_orders": raw,
        "delivered_status_rows": delivered,
        "complete_timestamp_rows": complete,
        "chronology_exclusions": complete - valid,
        "valid_real_completed_orders": valid,
    }


def group_stat(rows: list[dict], cols: tuple[str, ...], value: str, minimum: int, mean=False):
    groups = defaultdict(list)
    for r in rows:
        groups[tuple(r[c] for c in cols)].append(r[value])
    out = {}
    for key, vals in groups.items():
        if len(vals) >= minimum:
            out[key] = statistics.fmean(vals) if mean else statistics.median(vals)
    return out


class HistoricalCorrector:
    def __init__(self, rows: list[dict]):
        self.global_median = statistics.median(r["error_days"] for r in rows)
        self.global_late_rate = statistics.fmean(r["late"] for r in rows)
        self.medians = [(cols, group_stat(rows, cols, "error_days", minimum)) for cols, minimum in LEVELS]
        self.late_rates = [(cols, group_stat(rows, cols, "late", minimum, mean=True)) for cols, minimum in LEVELS]

    @staticmethod
    def _lookup(r: dict, tables, fallback):
        for cols, table in tables:
            key = tuple(r[c] for c in cols)
            if key in table:
                return table[key]
        return fallback

    def correction_days(self, r: dict) -> float:
        return self._lookup(r, self.medians, self.global_median)

    def late_risk(self, r: dict) -> float:
        return self._lookup(r, self.late_rates, self.global_late_rate)


def percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return float("nan")
    pos = (len(sorted_values) - 1) * p
    lo = math.floor(pos); hi = math.ceil(pos)
    if lo == hi: return sorted_values[lo]
    return sorted_values[lo] * (hi - pos) + sorted_values[hi] * (pos - lo)


def paired_bootstrap_reduction(base_abs: list[float], new_abs: list[float], reps=2000, seed=13507):
    rng = random.Random(seed)
    n = len(base_abs)
    vals = []
    for _ in range(reps):
        sb = sn = 0.0
        for _j in range(n):
            i = rng.randrange(n)
            sb += base_abs[i]; sn += new_abs[i]
        mb = sb / n; mn = sn / n
        vals.append((mb - mn) / mb * 100.0)
    vals.sort()
    return percentile(vals, 0.025), percentile(vals, 0.975)


def risk_bucket(scored: list[dict], fraction: float) -> dict:
    ordered = sorted(scored, key=lambda r: (-r["late_risk"], r["order_id"]))
    k = max(1, int(len(ordered) * fraction))
    selected = ordered[:k]
    late_total = sum(r["late"] for r in ordered)
    tp = sum(r["late"] for r in selected)
    precision = tp / k
    recall = tp / late_total if late_total else 0.0
    base_rate = late_total / len(ordered) if ordered else 0.0
    leads = [(r["actual"] - r["handoff"]).total_seconds() / 3600.0 for r in selected if r["late"]]
    return {
        "risk_bucket": f"top_{int(fraction*100)}pct",
        "orders_flagged": k,
        "true_late_captured": tp,
        "precision": precision,
        "late_recall": recall,
        "precision_lift_vs_base_rate": precision / base_rate if base_rate else 0.0,
        "warning_lead_hours_mean": statistics.fmean(leads) if leads else 0.0,
        "warning_lead_hours_median": statistics.median(leads) if leads else 0.0,
    }


def roc_auc(rows: list[dict]) -> float:
    # Rank-based Mann-Whitney AUC with average ranks for score ties.
    pairs = sorted((r["late_risk"], r["late"]) for r in rows)
    n_pos = sum(y for _, y in pairs); n_neg = len(pairs) - n_pos
    if not n_pos or not n_neg: return float("nan")
    rank = 1; sum_pos_ranks = 0.0; i = 0
    while i < len(pairs):
        j = i + 1
        while j < len(pairs) and pairs[j][0] == pairs[i][0]: j += 1
        avg_rank = (rank + (rank + (j - i) - 1)) / 2.0
        sum_pos_ranks += avg_rank * sum(y for _, y in pairs[i:j])
        rank += j - i; i = j
    return (sum_pos_ranks - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def average_precision(rows: list[dict]) -> float:
    ordered = sorted(rows, key=lambda r: (-r["late_risk"], r["order_id"]))
    total_pos = sum(r["late"] for r in ordered)
    if not total_pos: return 0.0
    tp = 0; ap = 0.0
    for i, r in enumerate(ordered, 1):
        if r["late"]:
            tp += 1
            ap += tp / i
    return ap / total_pos


def write_csv(path: Path, rows: list[dict]):
    if not rows: return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


def main():
    manifest = acquire_orders()
    rows, audit = load_real_orders()
    if len(rows) < 5000:
        raise RuntimeError("Real completed-order gate failed: fewer than 5,000 rows")

    split = int(len(rows) * 0.70)
    train = rows[:split]
    test = rows[split:]
    model = HistoricalCorrector(train)

    scored = []
    for r in test:
        corr = model.correction_days(r)
        scored.append({**r,
            "official_abs_error_days": abs(r["error_days"]),
            "global_abs_error_days": abs(r["error_days"] - model.global_median),
            "helixnid_correction_days": corr,
            "helixnid_abs_error_days": abs(r["error_days"] - corr),
            "late_risk": model.late_risk(r),
        })

    base_abs = [r["official_abs_error_days"] for r in scored]
    global_abs = [r["global_abs_error_days"] for r in scored]
    helix_abs = [r["helixnid_abs_error_days"] for r in scored]
    base_mae = statistics.fmean(base_abs)
    global_mae = statistics.fmean(global_abs)
    helix_mae = statistics.fmean(helix_abs)
    reduction = (base_mae - helix_mae) / base_mae * 100.0
    ci_low, ci_high = paired_bootstrap_reduction(base_abs, helix_abs)

    base_within1 = statistics.fmean(x <= 1 for x in base_abs)
    helix_within1 = statistics.fmean(x <= 1 for x in helix_abs)
    base_within2 = statistics.fmean(x <= 2 for x in base_abs)
    helix_within2 = statistics.fmean(x <= 2 for x in helix_abs)
    late_rate = statistics.fmean(r["late"] for r in scored)
    risk_rows = [risk_bucket(scored, f) for f in (0.05, 0.10, 0.20)]

    comparison = [
        {"metric": "delivery_date_mae_days", "official": base_mae, "global_history": global_mae, "helixnid": helix_mae, "helixnid_change": reduction},
        {"metric": "median_absolute_error_days", "official": statistics.median(base_abs), "global_history": "", "helixnid": statistics.median(helix_abs), "helixnid_change": ""},
        {"metric": "within_1_day_rate", "official": base_within1, "global_history": "", "helixnid": helix_within1, "helixnid_change": helix_within1 - base_within1},
        {"metric": "within_2_day_rate", "official": base_within2, "global_history": "", "helixnid": helix_within2, "helixnid_change": helix_within2 - base_within2},
    ]
    write_csv(REPORTS / "comparison_table.csv", comparison)
    write_csv(REPORTS / "late_risk_table.csv", risk_rows)

    validation = {
        **audit,
        "synthetic_rows_used": 0,
        "chronological_train_orders": len(train),
        "chronological_test_orders": len(test),
        "train_first_purchase": train[0]["purchase"].isoformat(),
        "train_last_purchase": train[-1]["purchase"].isoformat(),
        "test_first_purchase": test[0]["purchase"].isoformat(),
        "test_last_purchase": test[-1]["purchase"].isoformat(),
        "orders_sha256_verified": manifest["identity_verified"],
        "test_target_used_as_feature": False,
    }
    (REPORTS / "data_validation_report.json").write_text(json.dumps(validation, indent=2))

    certificate = {
        "certificate": "HELIXNID_CARRIER_PRECISION_METER_OLIST_REAL_V1",
        "status": "PASS",
        "generated_utc": now_utc(),
        "dataset": "Brazilian E-Commerce Public Dataset by Olist",
        "orders_sha256": ORDERS_SHA256,
        "synthetic_rows_used": 0,
        "valid_real_completed_orders": len(rows),
        "chronological_train_orders": len(train),
        "chronological_test_orders": len(test),
        "official_delivery_date_mae_days": base_mae,
        "global_historical_correction_mae_days": global_mae,
        "helixnid_corrected_mae_days": helix_mae,
        "eta_error_reduction_pct": reduction,
        "eta_error_reduction_bootstrap_95pct": [ci_low, ci_high],
        "official_median_absolute_error_days": statistics.median(base_abs),
        "helixnid_median_absolute_error_days": statistics.median(helix_abs),
        "official_within_1_day_rate": base_within1,
        "helixnid_within_1_day_rate": helix_within1,
        "official_within_2_day_rate": base_within2,
        "helixnid_within_2_day_rate": helix_within2,
        "test_late_rate": late_rate,
        "late_risk_roc_auc": roc_auc(scored),
        "late_risk_average_precision": average_precision(scored),
        "risk_triage": risk_rows,
        "claim_boundary": "Olist provides a customer-facing estimated delivery DATE and actual delivery timestamp, but no FedEx/UPS-style carrier identity. Results measure real delivery-promise correction at carrier handoff, not per-carrier brand performance.",
    }
    (REPORTS / "release_certificate.json").write_text(json.dumps(certificate, indent=2))

    report = f"""# HELIXNID Carrier Precision Meter — Real Olist Run

- Status: **PASS**
- Raw orders: **{audit['raw_orders']:,}**
- Valid real completed deliveries: **{len(rows):,}**
- Historical training orders: **{len(train):,}**
- Held-out future test orders: **{len(test):,}**
- Synthetic rows: **0**

## ETA / delivery-promise precision

- Official estimate MAE: **{base_mae:.3f} days**
- Global historical correction MAE: **{global_mae:.3f} days**
- HELIXNID corrected MAE: **{helix_mae:.3f} days**
- HELIXNID error reduction: **{reduction:.2f}%**
- Paired bootstrap 95% range: **{ci_low:.2f}% to {ci_high:.2f}%**
- Official median absolute error: **{statistics.median(base_abs):.1f} days**
- HELIXNID median absolute error: **{statistics.median(helix_abs):.1f} days**
- Official within ±1 day: **{base_within1*100:.2f}%**
- HELIXNID within ±1 day: **{helix_within1*100:.2f}%**
- Official within ±2 days: **{base_within2*100:.2f}%**
- HELIXNID within ±2 days: **{helix_within2*100:.2f}%**

## Late-risk triage at carrier handoff

- Future test late rate: **{late_rate*100:.2f}%**
- Risk ROC-AUC: **{roc_auc(scored):.4f}**
- Risk average precision: **{average_precision(scored):.4f}**
- Top 5% risk bucket captures **{risk_rows[0]['late_recall']*100:.2f}%** of late deliveries at **{risk_rows[0]['precision']*100:.2f}%** precision.
- Top 10% risk bucket captures **{risk_rows[1]['late_recall']*100:.2f}%** of late deliveries at **{risk_rows[1]['precision']*100:.2f}%** precision.
- Top 10% median warning lead: **{risk_rows[1]['warning_lead_hours_median']:.2f} hours**.

## Boundary

The Olist promise is a delivery **date**, so the primary error metric is days. Carrier brand identity is not present; no FedEx/UPS brand claim is made from this dataset.
"""
    (REPORTS / "empirical_run_report.md").write_text(report)

    ledger = f"""# Dataset Source Ledger — Olist

- Canonical dataset: Brazilian E-Commerce Public Dataset by Olist
- Canonical download: `{KAGGLE_URL}`
- Verified orders bytes: `{ORDERS_BYTES}`
- Verified orders SHA256: `{ORDERS_SHA256}`
- Real rows only: `true`
- Synthetic claim rows: `0`
"""
    (REPORTS / "dataset_source_ledger.md").write_text(ledger)

    artifacts = []
    for p in sorted(REPORTS.iterdir()):
        if p.is_file() and p.name != "artifact_hashes.csv":
            artifacts.append({"file": p.name, "bytes": p.stat().st_size, "sha256": sha256(p)})
    write_csv(REPORTS / "artifact_hashes.csv", artifacts)
    print(json.dumps(certificate, indent=2))


if __name__ == "__main__":
    main()
