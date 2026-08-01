# HELIXNID Carrier Precision Meter V1

## Final product

**Input**
- shipment ID
- ship/purchase time
- carrier handoff time
- original promised ETA
- optional carrier / service / destination

**Output**
- corrected ETA
- late probability
- risk band
- confidence
- historical support count
- warning window
- evidence/model identity

## Completed product chain

1. Robustness suite
2. Ten-model baseline battle
3. Business-value conversion
4. Product scoring engine
5. FastAPI plug-in API
6. Live dashboard
7. Independent LaDe real-industry replication runner
8. Amazon real-route held-out benchmark runner
9. Executive evidence/reviewer package builder
10. Master release certificate + artifact hash ledger

## Primary locked real evidence

- Dataset: Brazilian E-Commerce Public Dataset by Olist
- Real completed orders: **96,281**
- Chronological train: **67,396**
- Future held-out test: **28,885**
- Official delivery-date MAE: **13.446 days**
- HELIXNID corrected MAE: **4.116 days**
- ETA error reduction: **69.39%**
- Synthetic empirical claim rows: **0**

## Product locations

- Core empirical lane: `HELIXNID_EMPIRICAL_LANE_ONE/`
- Product 1-4: `HELIXNID_EMPIRICAL_LANE_ONE/product_1_4/`
- Product 5-6: `HELIXNID_EMPIRICAL_LANE_ONE/product_5_6/`
- Product 7-10: `HELIXNID_EMPIRICAL_LANE_ONE/product_7_10/`
- Final release builder: `HELIXNID_EMPIRICAL_LANE_ONE/product_7_10/09_10_final_release/build_final_release.py`

The final release workflow runs all executable stages, gathers certificates, hashes the release artifacts, and writes the master `RELEASE_CERTIFICATE.json`.
