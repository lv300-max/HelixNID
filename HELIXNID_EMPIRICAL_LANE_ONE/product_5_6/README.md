# HELIXNID Carrier Precision Meter — Product 5–6

This package turns the locked Product 4 scoring engine into a usable service and dashboard.

## 5 — Plug-in API

Folder: `05_api/`

Endpoints:

- `GET /health`
- `POST /score-shipment`
- `POST /correct-eta`
- `POST /late-risk`
- `POST /batch-score`
- `GET /certificate`
- `GET /metrics`

The API imports and uses the existing `carrier_precision_engine.py`. It does not copy or fork the scoring rules.

## 6 — Live dashboard

Folder: `06_dashboard/`

Screens:

- Today / live scoring
- High-risk shipment view
- Corrected ETA view
- Evidence / proof panel
- Operational counters

The dashboard calls the API over HTTP and does not calculate HELIXNID scores in the browser.

## Run locally

API:

```bash
python -m pip install -r HELIXNID_EMPIRICAL_LANE_ONE/product_5_6/05_api/requirements.txt
uvicorn app:app --app-dir HELIXNID_EMPIRICAL_LANE_ONE/product_5_6/05_api --host 0.0.0.0 --port 8000
```

Dashboard:

```bash
python -m http.server 8080 --directory HELIXNID_EMPIRICAL_LANE_ONE/product_5_6/06_dashboard
```

Then open `http://localhost:8080`.

## Evidence boundary

The API exposes the locked Olist empirical certificate. Olist does not identify FedEx/UPS/DHL carrier brands, so V1 carrier/service fields are accepted as integration fields but are not learned carrier-brand effects.
