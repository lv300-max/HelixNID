#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

HERE = Path(__file__).resolve()
LANE_ROOT = HERE.parents[2]
SRC = LANE_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import carrier_precision_engine as engine  # noqa: E402

LOCKED_CERT = LANE_ROOT / "reports_olist_eta" / "release_certificate.json"
MODEL_PATH = engine.MODEL_PATH

app = FastAPI(
    title="HELIXNID Carrier Precision API",
    version="1.0.0",
    description="Correct delivery promises and score late-delivery risk at carrier handoff.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class Shipment(BaseModel):
    model_config = ConfigDict(extra="allow")
    shipment_id: str | None = None
    ship_time: str | None = None
    purchase_time: str | None = None
    carrier_handoff_time: str
    carrier_eta_time: str | None = None
    promised_delivery_time: str | None = None
    carrier: str | None = None
    service: str | None = None
    destination: str | None = None
    destination_zip: str | None = None


class BatchRequest(BaseModel):
    shipments: list[Shipment] = Field(min_length=1, max_length=10000)


class RuntimeMetrics:
    def __init__(self):
        self.lock = Lock()
        self.started = datetime.now(timezone.utc)
        self.shipments_scored = 0
        self.high_risk = 0
        self.elevated_or_higher = 0
        self.total_abs_correction_days = 0.0
        self.batch_requests = 0

    def record(self, scored: dict[str, Any]):
        with self.lock:
            self.shipments_scored += 1
            band = scored.get("late_risk_band")
            if band == "HIGH":
                self.high_risk += 1
            if band in {"HIGH", "ELEVATED"}:
                self.elevated_or_higher += 1
            self.total_abs_correction_days += abs(float(scored.get("helixnid_correction_days", 0.0)))

    def record_batch(self):
        with self.lock:
            self.batch_requests += 1

    def snapshot(self):
        with self.lock:
            n = self.shipments_scored
            return {
                "service_started_utc": self.started.isoformat(),
                "shipments_scored": n,
                "high_risk_shipments": self.high_risk,
                "elevated_or_higher_shipments": self.elevated_or_higher,
                "average_absolute_correction_days": self.total_abs_correction_days / n if n else 0.0,
                "batch_requests": self.batch_requests,
            }


metrics = RuntimeMetrics()
_model_cache: dict[str, Any] | None = None
_model_lock = Lock()


def ensure_model() -> dict[str, Any]:
    global _model_cache
    with _model_lock:
        if _model_cache is not None:
            return _model_cache
        if not MODEL_PATH.exists():
            _model_cache = engine.build_model()
        else:
            _model_cache = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
        return _model_cache


def score_payload(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        result = engine.score(payload, ensure_model())
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    metrics.record(result)
    return result


def locked_certificate() -> dict[str, Any]:
    if not LOCKED_CERT.exists():
        return {
            "status": "MODEL_AVAILABLE_CERTIFICATE_NOT_FOUND",
            "model_path": str(MODEL_PATH),
        }
    return json.loads(LOCKED_CERT.read_text(encoding="utf-8"))


@app.get("/")
def root():
    return {
        "product": "HELIXNID Carrier Precision Meter",
        "api": "v1",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health():
    model = ensure_model()
    return {
        "status": "ok",
        "model": model.get("model"),
        "dataset_sha256": model.get("dataset_sha256"),
        "trained_real_completed_orders": model.get("trained_real_completed_orders"),
        "synthetic_rows": model.get("synthetic_rows"),
    }


@app.post("/score-shipment")
def score_shipment(shipment: Shipment):
    return score_payload(shipment.model_dump(exclude_none=True))


@app.post("/correct-eta")
def correct_eta(shipment: Shipment):
    r = score_payload(shipment.model_dump(exclude_none=True))
    return {
        "shipment_id": r.get("shipment_id"),
        "original_eta": r["original_eta"],
        "helixnid_corrected_eta": r["helixnid_corrected_eta"],
        "helixnid_correction_days": r["helixnid_correction_days"],
        "confidence": r["confidence"],
        "matched_history_rows": r["matched_history_rows"],
        "model": r["model"],
        "dataset_sha256": r["dataset_sha256"],
    }


@app.post("/late-risk")
def late_risk(shipment: Shipment):
    r = score_payload(shipment.model_dump(exclude_none=True))
    return {
        "shipment_id": r.get("shipment_id"),
        "late_probability": r["late_probability"],
        "late_risk_band": r["late_risk_band"],
        "warning_window_hours_to_original_eta": r["warning_window_hours_to_original_eta"],
        "confidence": r["confidence"],
        "matched_history_rows": r["matched_history_rows"],
    }


@app.post("/batch-score")
def batch_score(request: BatchRequest):
    metrics.record_batch()
    results = [score_payload(s.model_dump(exclude_none=True)) for s in request.shipments]
    high = sum(r["late_risk_band"] == "HIGH" for r in results)
    elevated = sum(r["late_risk_band"] in {"HIGH", "ELEVATED"} for r in results)
    return {
        "count": len(results),
        "high_risk": high,
        "elevated_or_higher": elevated,
        "results": results,
    }


@app.get("/certificate")
def certificate():
    cert = locked_certificate()
    return {
        "product": "HELIXNID Carrier Precision Meter",
        "empirical_certificate": cert,
        "api_scope": "delivery-promise correction and late-risk scoring at carrier handoff",
        "carrier_brand_boundary": "Olist V1 has no FedEx/UPS/DHL carrier identity; carrier/service fields are integration passthrough fields until carrier-labelled evidence is acquired.",
    }


@app.get("/metrics")
def runtime_metrics():
    return metrics.snapshot()
