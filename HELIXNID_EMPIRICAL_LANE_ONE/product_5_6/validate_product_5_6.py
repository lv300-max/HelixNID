#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API = ROOT / "05_api"
DASH = ROOT / "06_dashboard"
LANE = ROOT.parent
SRC = LANE / "src"
if str(API) not in sys.path:
    sys.path.insert(0, str(API))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import app as api_app  # noqa: E402

REQUIRED_ROUTES = {
    "/health",
    "/score-shipment",
    "/correct-eta",
    "/late-risk",
    "/batch-score",
    "/carrier-report",
    "/route-report",
    "/certificate",
    "/metrics",
}
REQUIRED_DASH = {"index.html", "styles.css", "app.js"}


def main():
    routes = {getattr(r, "path", "") for r in api_app.app.routes}
    missing_routes = sorted(REQUIRED_ROUTES - routes)
    missing_dash = sorted(name for name in REQUIRED_DASH if not (DASH / name).exists())
    index = (DASH / "index.html").read_text(encoding="utf-8")
    js = (DASH / "app.js").read_text(encoding="utf-8")
    dashboard_contract = {
        "calls_score_shipment": "/score-shipment" in js,
        "calls_metrics": "/metrics" in js,
        "calls_certificate": "/certificate" in js,
        "has_live_score_form": "scoreForm" in index,
        "has_evidence_panel": "Locked empirical evidence" in index,
    }
    passed = not missing_routes and not missing_dash and all(dashboard_contract.values())
    certificate = {
        "certificate": "HELIXNID_CARRIER_PRECISION_PRODUCT_5_6_BUILD_V1",
        "status": "PASS" if passed else "FAIL",
        "api_required_routes": sorted(REQUIRED_ROUTES),
        "api_routes_found": sorted(x for x in routes if x in REQUIRED_ROUTES),
        "missing_api_routes": missing_routes,
        "dashboard_required_files": sorted(REQUIRED_DASH),
        "missing_dashboard_files": missing_dash,
        "dashboard_contract": dashboard_contract,
        "scoring_source": "HELIXNID_EMPIRICAL_LANE_ONE/src/carrier_precision_engine.py",
        "browser_scoring_logic": False,
        "empirical_claim_source": "HELIXNID_EMPIRICAL_LANE_ONE/reports_olist_eta/release_certificate.json",
    }
    out = ROOT / "PRODUCT_5_6_BUILD_CERTIFICATE.json"
    out.write_text(json.dumps(certificate, indent=2), encoding="utf-8")
    print(json.dumps(certificate, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
