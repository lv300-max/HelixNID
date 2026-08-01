# HELIXNID Carrier Precision Meter — Deployment

## Stack

- API: FastAPI on port 8000
- Dashboard: nginx static site on port 8080
- Persistence: SQLite volume `helixnid_runtime`
- Model: HELIXNID Carrier Precision Model V1, built from the verified Olist source when no cached model artifact exists

## One command

```bash
docker compose -f HELIXNID_EMPIRICAL_LANE_ONE/product_5_6/docker-compose.yml up --build -d
```

## Product endpoints

- `POST /score-shipment`
- `POST /correct-eta`
- `POST /late-risk`
- `POST /batch-score`
- `POST /batch-score-csv`
- `POST /carrier-report`
- `POST /route-report`
- `GET /recent`
- `GET /export.csv`
- `GET /metrics`
- `GET /certificate`
- `GET /health`

## Persistent evidence log

Every production score is stored in SQLite with:

- score timestamp
- shipment ID
- carrier/service/destination passthrough fields
- late probability and risk band
- correction days
- confidence
- complete input JSON
- complete output JSON

The database is mounted outside the API container and survives container replacement.

## CSV ingestion

A UTF-8 CSV can be posted to `/batch-score-csv`. Supported shipment fields are the same as the JSON API, including:

`shipment_id, ship_time, purchase_time, carrier_handoff_time, carrier_eta_time, promised_delivery_time, carrier, service, destination, destination_zip`

Maximum default batch size: 10,000 rows. Override with `HELIXNID_MAX_BATCH`.

## Export

`GET /export.csv` returns the persisted score ledger as CSV.

## Evidence boundary

The locked 69.39% delivery-promise correction result is Olist evidence. Olist does not expose FedEx/UPS/DHL-style carrier identity. Carrier and service are accepted as integration fields, but V1 does not claim carrier-brand-specific learned effects.
