# HELIXNID Carrier Precision Meter — Product 1–4

This folder is the product-facing execution package built on the locked real Olist empirical lane.

## 1 — Robustness attack

Output folder: `01_robustness/`

Runs:
- 50/50 chronological split
- 60/40 chronological split
- 70/30 chronological split
- 80/20 chronological split
- rolling-origin future blocks
- calendar-month future holdouts
- stress segments

Main files:
- `robustness_results.csv`
- `robustness_certificate.json`
- `ROBUSTNESS_REPORT.md`

## 2 — Ten-model baseline battle

Output folder: `02_baseline_battle/`

Compares:
1. Official promise
2. Global median correction
3. Recent-5000 median
4. Linear regression
5. Ridge regression
6. Random forest
7. Extra trees
8. Gradient boosting
9. XGBoost
10. HELIXNID historical hierarchy

Main files:
- `BENCHMARK_LEADERBOARD.csv`
- `baseline_battle_certificate.json`
- `BASELINE_BATTLE_REPORT.md`

## 3 — Business-value conversion

Output folder: `03_business_value/`

Converts the locked empirical rates into operational counts for:
- 1,000 shipments
- 10,000 shipments
- 100,000 shipments

Measures:
- ETA error-days removed
- extra shipments inside ±1 day
- extra shipments inside ±2 days
- high-risk shipments flagged
- late shipments captured
- warning lead time

No dollar claim is invented. Buyer-specific money inputs remain separate.

Main files:
- `business_scale_table.csv`
- `business_value_certificate.json`
- `BUSINESS_VALUE_REPORT.md`

## 4 — Product scoring engine

Output folder: `04_scoring_engine/`

Final product input:
- shipment ID
- ship/purchase time
- carrier handoff time
- original ETA
- optional carrier
- optional service
- optional destination

Final product output:
- original ETA
- HELIXNID corrected ETA
- correction days
- late probability
- late-risk band
- confidence
- matched history rows
- warning window
- model and evidence hash

Model artifact:
- `carrier_precision_model_v1.json`

## One-command build

`python HELIXNID_EMPIRICAL_LANE_ONE/src/run_product_1_4.py`

The command executes all four stages and creates:

`PRODUCT_1_4_CERTIFICATE.json`

Raw empirical claim data remain real Olist completed orders. Synthetic empirical rows = 0.
