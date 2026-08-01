# HELIXNID Product Phases 5–9

This package completes the product path beyond the locked Olist evidence lane.

## 5 — Carrier-labelled evidence

- Validated completed-shipment schema
- JSON and CSV import endpoints
- Chronology validation
- FedEx, USPS, generic, and Pakket webhook normalizers
- Real USPS public aggregate evidence record
- Carrier-specific model gate at 5,000 valid completed rows

Required row-level fields:

- shipment ID
- carrier
- carrier handoff time
- original promised delivery time
- actual delivery time

No carrier-specific accuracy claim is emitted before the gate passes.

## 6 — Live tracking intelligence

Every tracking event can update:

- live ETA
- live late probability
- live risk band
- scan-silence hours
- latest status
- operational reasons

The locked historical model remains the base. Event adjustments are separately identified as auditable operational rules until carrier-labelled replay validates them.

## 7 — Enterprise measurement

Endpoints provide:

- overall shipment summary
- carrier/service/destination breakdowns
- risk concentration
- live alerts
- tracking-event coverage
- carrier-evidence accumulation

The enterprise dashboard is `product_5_6/06_dashboard/enterprise.html`.

## 8 — Financial measurement

The financial calculator accepts customer-provided:

- shipment volume
- support-contact rate and cost
- refund/replacement rate and cost
- late-compensation rate and cost
- intervention success rate

No dollar value is invented or guaranteed.

## 9 — General precision engine

The domain-neutral engine accepts:

- historical expected values
- actual values
- context columns
- chronological replay rows

It returns:

- corrected expected value
- correction amount
- confidence
- matched-history count
- replay MAE reduction
- model hash

This allows HELIXNID precision architecture to be applied to logistics, maintenance, manufacturing, inventory, energy, and other expected-vs-actual systems.

## API

Run the final API surface with:

`uvicorn app_v2:app --app-dir HELIXNID_EMPIRICAL_LANE_ONE/product_5_6/05_api --host 0.0.0.0 --port 8000`

Or use the Docker Compose deployment already included in Product 5–6.
