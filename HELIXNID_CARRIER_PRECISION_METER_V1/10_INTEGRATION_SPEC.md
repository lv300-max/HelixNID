# Integration Specification

## Required live fields
- `shipment_id`
- `ship_time` or `purchase_time`
- `carrier_handoff_time`
- `carrier_eta_time` or `promised_delivery_time`

## Optional fields
- `carrier`
- `service`
- `destination`
- `destination_zip`

## Flow
Carrier / commerce system -> HELIXNID API -> corrected ETA + late risk -> dashboard / merchant workflow.

Carrier and service are already accepted by the interface. Carrier-brand-specific learned corrections remain evidence-gated until completed carrier-labelled history is connected.
