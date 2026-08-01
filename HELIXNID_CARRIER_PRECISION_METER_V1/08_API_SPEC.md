# API Specification

Implementation: `HELIXNID_EMPIRICAL_LANE_ONE/product_5_6/05_api/app.py`

Endpoints:
- `POST /score-shipment`
- `POST /correct-eta`
- `POST /late-risk`
- `POST /batch-score`
- `POST /carrier-report`
- `POST /route-report`
- `GET /metrics`
- `GET /certificate`
- `GET /health`

Batch limit: **10,000 shipments** per request.

The API calls the Product 4 scoring engine directly. It does not contain a second scoring model.
