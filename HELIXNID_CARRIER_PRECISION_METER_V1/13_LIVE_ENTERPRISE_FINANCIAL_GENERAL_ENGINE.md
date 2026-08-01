# HELIXNID Precision Engine — Final Operating Guide

## Start the product

Use Docker Compose from:

`HELIXNID_EMPIRICAL_LANE_ONE/product_5_6/docker-compose.yml`

API entrypoint:

`app_v2:app`

Dashboards:

- Shipment Meter: `/index.html`
- Enterprise Console: `/enterprise.html`

## Shipment scoring

`POST /score-shipment`

Required timing fields:

- `purchase_time` or `ship_time`
- `carrier_handoff_time`
- `promised_delivery_time` or `carrier_eta_time`

The result includes corrected ETA, late probability, risk band, confidence, warning window, history match, model name, and dataset hash.

## Authorized carrier events

`POST /carrier-webhook/fedex`

`POST /carrier-webhook/usps`

`POST /carrier-webhook/pakket`

`POST /carrier-webhook/generic`

HELIXNID normalizes provider events and updates the shipment's live state. The shipment must first be scored so the event layer has an empirical base prediction.

Direct normalized event endpoint:

`POST /tracking-event`

Live state:

`GET /shipment/{shipment_id}/live`

## Carrier-labelled evidence

Completed real shipments can be imported through:

- `POST /carrier-evidence/import`
- `POST /carrier-evidence/import-csv?source=SOURCE_NAME`

Required fields:

- shipment ID
- carrier
- carrier handoff time
- original promised delivery time
- actual delivery time

Gate state:

`GET /carrier-evidence/status`

Carrier-specific model claims remain locked until 5,000 valid completed rows pass chronology validation.

## Enterprise measurement

- `GET /enterprise/summary`
- `GET /enterprise/breakdown?group_by=carrier`
- `GET /enterprise/breakdown?group_by=service`
- `GET /enterprise/breakdown?group_by=destination`
- `GET /enterprise/alerts`

These endpoints measure corrections, risk concentration, event coverage, scan silence, active alerts, and carrier-evidence accumulation.

## Financial scenarios

`POST /financial-value`

Inputs are customer controlled:

- shipment volume
- intervention success rate
- support contact rate and cost
- refund/replacement rate and cost
- late compensation rate and cost

The output is a transparent scenario calculation. It is not a guaranteed savings claim.

## General precision engine

- `POST /precision/fit`
- `POST /precision/score`
- `POST /precision/replay`

The caller supplies expected values, actual values, context columns, and units. HELIXNID learns historical residual correction tables, returns a model hash, and evaluates chronological future performance.

## Evidence boundaries

- 69.39% remains the locked Olist delivery-promise correction result.
- USPS FY2026 Q1 is official aggregate carrier evidence only.
- Live event adjustments are auditable operational rules until carrier-labelled replay validates them.
- LaDe and Amazon remain separate real operational runners without generated certificates in the present execution environment.
