#!/usr/bin/env python3
"""Reusable HELIXNID expected-vs-actual precision engine.

The engine is domain-neutral: it learns historical residual medians at progressively
broader context levels, scores new expected values, and replays completed rows. It is
intended for logistics, maintenance, manufacturing, inventory, energy, and other lanes.
"""
from __future__ import annotations

import hashlib
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _key(row: dict[str, Any], cols: list[str]) -> tuple[str, ...]:
    return tuple(str(row.get(c, "UNKNOWN")) for c in cols)


def fit(payload: dict[str, Any]) -> dict[str, Any]:
    rows = list(payload.get("rows") or [])
    expected_field = str(payload.get("expected_field") or "expected")
    actual_field = str(payload.get("actual_field") or "actual")
    context_levels = [list(x) for x in payload.get("context_levels") or []]
    minimum_counts = list(payload.get("minimum_counts") or [])
    if not rows:
        raise ValueError("rows are required")
    if len(minimum_counts) not in {0, len(context_levels)}:
        raise ValueError("minimum_counts must be empty or match context_levels")
    if not minimum_counts:
        minimum_counts = [20] * len(context_levels)

    residuals = []
    clean_rows = []
    for index, row in enumerate(rows, 1):
        try:
            expected = float(row[expected_field])
            actual = float(row[actual_field])
        except Exception as exc:
            raise ValueError(f"row {index} has invalid expected/actual values") from exc
        clean = dict(row)
        clean["_residual"] = actual - expected
        residuals.append(clean["_residual"])
        clean_rows.append(clean)

    levels = []
    for cols, minimum in zip(context_levels, minimum_counts):
        groups: dict[tuple[str, ...], list[float]] = defaultdict(list)
        for row in clean_rows:
            groups[_key(row, cols)].append(float(row["_residual"]))
        table = [
            {"key": list(key), "median_residual": statistics.median(vals), "count": len(vals)}
            for key, vals in sorted(groups.items()) if len(vals) >= int(minimum)
        ]
        levels.append({"columns": cols, "minimum_count": int(minimum), "table": table})

    artifact = {
        "model": "HELIXNID_GENERAL_PRECISION_ENGINE_V1",
        "built_utc": utc_now(),
        "domain": str(payload.get("domain") or "generic"),
        "unit": str(payload.get("unit") or "numeric_units"),
        "expected_field": expected_field,
        "actual_field": actual_field,
        "training_rows": len(clean_rows),
        "global_median_residual": statistics.median(residuals),
        "levels": levels,
        "scope": "historical residual correction with deterministic hierarchical fallbacks",
    }
    canonical = json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode()
    artifact["model_sha256"] = hashlib.sha256(canonical).hexdigest()
    return artifact


def score(row: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    expected_field = model["expected_field"]
    expected = float(row[expected_field])
    correction = float(model["global_median_residual"])
    matched_count = int(model["training_rows"])
    matched_level: list[str] = ["global"]
    for level in model.get("levels", []):
        lookup = {tuple(item["key"]): item for item in level["table"]}
        item = lookup.get(_key(row, level["columns"]))
        if item:
            correction = float(item["median_residual"])
            matched_count = int(item["count"])
            matched_level = list(level["columns"])
            break
    corrected = expected + correction
    confidence = "HIGH" if matched_count >= 100 else "MEDIUM" if matched_count >= 20 else "LOW"
    return {
        "expected": expected,
        "corrected_expected": corrected,
        "correction": correction,
        "unit": model.get("unit"),
        "confidence": confidence,
        "matched_history_rows": matched_count,
        "matched_level": matched_level,
        "model": model["model"],
        "model_sha256": model["model_sha256"],
        "domain": model.get("domain"),
    }


def replay(payload: dict[str, Any]) -> dict[str, Any]:
    rows = list(payload.get("rows") or [])
    train_fraction = float(payload.get("train_fraction", 0.70))
    if not 0.1 <= train_fraction <= 0.9:
        raise ValueError("train_fraction must be between 0.1 and 0.9")
    if len(rows) < 100:
        raise ValueError("at least 100 rows are required for replay")
    cut = int(len(rows) * train_fraction)
    fit_payload = dict(payload)
    fit_payload["rows"] = rows[:cut]
    model = fit(fit_payload)
    expected_field = model["expected_field"]
    actual_field = model["actual_field"]
    base_errors = []
    corrected_errors = []
    improved = worsened = tied = 0
    for row in rows[cut:]:
        actual = float(row[actual_field])
        base_error = abs(actual - float(row[expected_field]))
        result = score(row, model)
        corrected_error = abs(actual - float(result["corrected_expected"]))
        base_errors.append(base_error)
        corrected_errors.append(corrected_error)
        if corrected_error < base_error:
            improved += 1
        elif corrected_error > base_error:
            worsened += 1
        else:
            tied += 1
    base_mae = statistics.fmean(base_errors)
    corrected_mae = statistics.fmean(corrected_errors)
    return {
        "certificate": "HELIXNID_GENERAL_PRECISION_REPLAY_V1",
        "domain": model.get("domain"),
        "unit": model.get("unit"),
        "training_rows": cut,
        "future_test_rows": len(rows) - cut,
        "baseline_mae": base_mae,
        "corrected_mae": corrected_mae,
        "error_reduction_pct": ((base_mae - corrected_mae) / base_mae * 100.0) if base_mae else 0.0,
        "improved": improved,
        "worsened": worsened,
        "tied": tied,
        "improved_rate": improved / len(base_errors),
        "model_sha256": model["model_sha256"],
        "claim_boundary": "This certificate applies only to the supplied chronological rows and declared expected/actual fields.",
    }
