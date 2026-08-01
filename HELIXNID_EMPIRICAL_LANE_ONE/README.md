# HELIXNID Empirical Lane One

## Product

**HELIXNID Carrier Precision Meter**

## Lane One-B — Real delivery-promise precision — PASS

Real source: **Brazilian E-Commerce Public Dataset by Olist**.

- Raw orders: **99,441**
- Valid real completed deliveries: **96,281**
- Historical training orders: **67,396**
- Held-out future test orders: **28,885**
- Synthetic claim rows: **0**
- Official delivery-date MAE: **13.446 days**
- HELIXNID corrected MAE: **4.116 days**
- ETA error reduction: **69.39%**
- Paired bootstrap 95% range: **68.97%–69.77%**
- Official within ±1 day: **4.54%**
- HELIXNID within ±1 day: **30.18%**
- Official within ±2 days: **7.27%**
- HELIXNID within ±2 days: **45.41%**

### Late-risk triage at carrier handoff

- Future late rate: **4.32%**
- ROC-AUC: **0.7283**
- Top 5% risk bucket captures **33.28%** of late deliveries.
- Top 10% risk bucket captures **42.90%** of late deliveries.
- Top 10% precision lift: **4.29×** over the base late rate.
- Top 10% median warning lead: **127.13 hours**.

### Evidence package

- `reports_olist_eta/release_certificate.json`
- `reports_olist_eta/empirical_run_report.md`
- `reports_olist_eta/comparison_table.csv`
- `reports_olist_eta/late_risk_table.csv`
- `reports_olist_eta/data_validation_report.json`
- `reports_olist_eta/acquisition_manifest.json`
- `reports_olist_eta/dataset_source_ledger.md`
- `reports_olist_eta/artifact_hashes.csv`

Runner: `src/helixnid_olist_eta_benchmark.py`

## Lane One-A — Real last-mile route precision

Source: **2021 Amazon Last Mile Routing Research Challenge**.

- 6,112 historical training routes.
- 3,072 held-out evaluation routes.
- Synthetic claim rows: **0**.
- Runner: `src/helixnid_last_mile_benchmark.py`

This remains a separate route/stop-order benchmark. It is not mixed into the Olist delivery-promise result above.

## Claim boundary

Olist supplies a customer-facing estimated delivery **date** and an actual delivery timestamp. It does not expose FedEx/UPS-style carrier brand identity. The locked 69.39% result is therefore a real delivery-promise correction result at carrier handoff, not a named-carrier brand claim.
