# Carrier Connector and Public Evidence Ledger

## FedEx

Official interface: Basic Integrated Visibility / Track API.

HELIXNID contract supports:

- tracking number
- service type
- scan events
- estimated delivery time window
- actual delivery timestamp
- delay status and exception information

HELIXNID does not bypass FedEx authorization. Row-level evidence becomes eligible only when the original estimate is retained before actual delivery.

## USPS

Official interface: Logistics Shipments 3.0 for authorized logistics partners.

HELIXNID contract supports:

- external load number
- appointment identifier
- event timestamps
- estimated arrival
- status
- facility/location information
- delay reason

HELIXNID does not bypass USPS OAuth or scope requirements.

## Generic / Pakket

The generic normalizer accepts a carrier name, tracking number, estimated delivery, normalized status, and event timeline from an authorized multi-carrier provider.

## Locked real public carrier evidence

File:

`HELIXNID_EMPIRICAL_LANE_ONE/product_5_9/public_carrier_evidence/USPS_FY2026_Q1_SERVICE_PERFORMANCE.json`

Official USPS national Single-Piece First-Class Mail performance for pieces delivered from October 1 through December 31, 2025:

- Two-day on time: 84.7%
- Three-day on time: 78.4%
- Four-day on time: 74.7%
- Five-day on time: 87.4%
- Within standard plus three days: at least 96.8%

This evidence is carrier-labelled and real, but aggregate. It is not used as row-level training or validation evidence.

## Row-level carrier evidence lock

Carrier-specific accuracy measurement requires at least 5,000 completed real shipments with:

- carrier
- service when available
- carrier handoff
- original carrier promise
- actual delivery
- optional event history

The ingestion layer validates chronology and exposes the current gate state through `/carrier-evidence/status`.
