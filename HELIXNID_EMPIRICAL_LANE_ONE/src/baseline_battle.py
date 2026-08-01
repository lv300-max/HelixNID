#!/usr/bin/env python3
"""HELIXNID Product 2 — ten-model baseline battle on the same real future holdout."""
from __future__ import annotations

import csv
import json
import statistics
import time
from pathlib import Path

import numpy as np
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression, Ridge

import helixnid_olist_eta_benchmark as core

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "product_1_4" / "02_baseline_battle"
OUT.mkdir(parents=True, exist_ok=True)


def feature_row(r):
    promise_days = (r["estimate"] - r["purchase"]).total_seconds() / 86400.0
    handoff_days = (r["handoff"] - r["purchase"]).total_seconds() / 86400.0
    slack_days = (r["estimate"] - r["handoff"]).total_seconds() / 86400.0
    return [
        promise_days,
        handoff_days,
        slack_days,
        float(r["purchase"].weekday()),
        float(r["purchase"].month),
        r["purchase"].timestamp() / 86400.0,
    ]


def metrics(name, y, pred, train_seconds=0.0, predict_seconds=0.0, notes=""):
    errors = np.abs(y - pred)
    base = np.abs(y)
    base_mae = float(np.mean(base))
    model_mae = float(np.mean(errors))
    return {
        "model": name,
        "mae_days": model_mae,
        "median_abs_error_days": float(np.median(errors)),
        "within_1_day_rate": float(np.mean(errors <= 1.0)),
        "within_2_day_rate": float(np.mean(errors <= 2.0)),
        "error_reduction_vs_official_pct": float((base_mae-model_mae)/base_mae*100.0),
        "train_seconds": float(train_seconds),
        "predict_seconds": float(predict_seconds),
        "notes": notes,
    }


def fit_predict(name, model, X_train, y_train, X_test):
    t0 = time.perf_counter(); model.fit(X_train, y_train); t1 = time.perf_counter()
    pred = model.predict(X_test); t2 = time.perf_counter()
    return metrics(name, y_test_global, pred, t1-t0, t2-t1)


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


def main():
    global y_test_global
    manifest = core.acquire_orders()
    rows, audit = core.load_real_orders()
    cut = int(len(rows) * 0.70)
    train, test = rows[:cut], rows[cut:]
    X_train = np.asarray([feature_row(r) for r in train], dtype=float)
    X_test = np.asarray([feature_row(r) for r in test], dtype=float)
    y_train = np.asarray([r["error_days"] for r in train], dtype=float)
    y_test = np.asarray([r["error_days"] for r in test], dtype=float)
    y_test_global = y_test

    results = []
    # 1. Official promise = no correction.
    results.append(metrics("01 Official promise", y_test, np.zeros_like(y_test), notes="Raw marketplace promised delivery date"))
    # 2. Global historical median.
    global_median = float(np.median(y_train))
    results.append(metrics("02 Global median correction", y_test, np.full_like(y_test, global_median)))
    # 3. Recent-history median.
    recent_median = float(np.median(y_train[-5000:]))
    results.append(metrics("03 Recent-5000 median", y_test, np.full_like(y_test, recent_median)))

    # 4-8. Standard regression competitors.
    competitors = [
        ("04 Linear regression", LinearRegression()),
        ("05 Ridge regression", Ridge(alpha=1.0)),
        ("06 Random forest", RandomForestRegressor(n_estimators=160, min_samples_leaf=8, random_state=13507, n_jobs=-1)),
        ("07 Extra trees", ExtraTreesRegressor(n_estimators=160, min_samples_leaf=8, random_state=13507, n_jobs=-1)),
        ("08 Gradient boosting", GradientBoostingRegressor(n_estimators=160, learning_rate=0.05, max_depth=3, random_state=13507, loss="absolute_error")),
    ]
    for name, model in competitors:
        results.append(fit_predict(name, model, X_train, y_train, X_test))

    # 9. XGBoost when installed; deterministic sklearn fallback otherwise.
    try:
        from xgboost import XGBRegressor
        xgb = XGBRegressor(
            n_estimators=220, max_depth=6, learning_rate=0.04, subsample=0.85,
            colsample_bytree=0.9, objective="reg:absoluteerror", random_state=13507,
            n_jobs=-1, tree_method="hist"
        )
        results.append(fit_predict("09 XGBoost", xgb, X_train, y_train, X_test))
    except Exception as exc:
        fallback = HistGradientBoostingRegressor(max_iter=220, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0, random_state=13507, loss="absolute_error")
        row = fit_predict("09 HistGradientBoosting fallback", fallback, X_train, y_train, X_test)
        row["notes"] = f"XGBoost unavailable: {type(exc).__name__}"
        results.append(row)

    # 10. Locked HELIXNID hierarchical correction.
    t0 = time.perf_counter(); helix = core.HistoricalCorrector(train); t1 = time.perf_counter()
    pred = np.asarray([helix.correction_days(r) for r in test], dtype=float); t2 = time.perf_counter()
    results.append(metrics("10 HELIXNID historical hierarchy", y_test, pred, t1-t0, t2-t1, "Locked permission-safe empirical corrector"))

    ranked = sorted(results, key=lambda r: (r["mae_days"], r["model"]))
    for i, row in enumerate(ranked, 1):
        row["rank"] = i
    # Put rank first for easy reading.
    ranked = [{"rank": r.pop("rank"), **r} for r in ranked]
    write_csv(OUT / "BENCHMARK_LEADERBOARD.csv", ranked)

    helix_row = next(r for r in ranked if r["model"].startswith("10 HELIXNID"))
    winner = ranked[0]
    certificate = {
        "certificate": "HELIXNID_CARRIER_PRECISION_BASELINE_BATTLE_V1",
        "dataset_sha256": manifest["orders_sha256"],
        "synthetic_rows": 0,
        "chronological_train_rows": len(train),
        "chronological_future_test_rows": len(test),
        "models_compared": len(ranked),
        "winner": winner["model"],
        "winner_mae_days": winner["mae_days"],
        "helixnid_rank": helix_row["rank"],
        "helixnid_mae_days": helix_row["mae_days"],
        "helixnid_error_reduction_vs_official_pct": helix_row["error_reduction_vs_official_pct"],
        "leaderboard": ranked,
    }
    (OUT / "baseline_battle_certificate.json").write_text(json.dumps(certificate, indent=2), encoding="utf-8")
    lines = [
        "# HELIXNID 10-Model Baseline Battle", "",
        f"- Real future test orders: **{len(test):,}**",
        f"- Winner: **{winner['model']}** — {winner['mae_days']:.3f} days MAE",
        f"- HELIXNID rank: **#{helix_row['rank']} of {len(ranked)}**",
        f"- HELIXNID MAE: **{helix_row['mae_days']:.3f} days**",
        "", "## Ranking", "",
    ]
    for r in ranked:
        lines.append(f"{r['rank']}. {r['model']} — {r['mae_days']:.3f} days MAE — {r['error_reduction_vs_official_pct']:.2f}% vs official")
    (OUT / "BASELINE_BATTLE_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({k:v for k,v in certificate.items() if k != "leaderboard"}, indent=2))


if __name__ == "__main__":
    main()
