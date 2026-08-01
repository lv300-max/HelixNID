# HELIXNID Precision Engine V1 — Evidence Leaderboard

## Locked real evidence

| Lane | Real evaluation | Result | State |
|---|---:|---|---|
| Olist delivery-promise correction | 28,885 future orders | 13.446 → 4.116 days MAE; **69.39% reduction** | LOCKED PASS |
| Robustness attack | 17 normal future holdouts + 6 stress slices | normal-holdout floor **25.72%**, median **63.33%**, max **74.95%** | LOCKED PASS |
| 10-model battle | 28,885 future orders | HELIXNID **#3/10**, 4.116 d; XGBoost #1 at 3.854 d | LOCKED |
| Historical replay | 28,885 future shipments | **24,590 improved**, 269,503 absolute error-days removed | LOCKED PASS |
| LaDe-D external replication | 9,425 future real tasks | 107.214 → 100.714 minutes MAE; **6.06% reduction** | LOCKED PASS |
| Amazon adjacent-edge benchmark | 3,052 held-out real routes | 0.248055 → 0.296437 recall; **19.50% improvement**; 73.07% route win rate | LOCKED PASS |

## Exact pressure points retained

- Olist `late_only` stress slice: HELIXNID 14.272 d MAE versus official 7.158 d, **-99.38%** relative change.
- Gap to XGBoost on the fixed Olist future holdout: **0.263 day MAE**.
- Amazon pair-order accuracy: **3.33% lower** than geographic nearest-neighbor.
- Amazon normalized position MAE: **5.87% worse**.
- Amazon rank correlation is lower; the current Amazon result is a local-edge gain, not a global route-order win.

## External-lane boundaries

- **LaDe-D:** independent accept-to-delivery task timing. It does not contain a customer-facing promised ETA.
- **Amazon:** route/stop-order precision. It does not contain carrier promised ETA versus actual delivery timestamps.
- **USPS FY2026 Q1:** official carrier-labelled aggregate performance only; no row-level shipment model claim.

## Deployment state

- FastAPI v2.0
- offline embedded Olist model
- shipment dashboard
- enterprise dashboard
- SQLite persistence
- JSON and CSV ingestion/export
- authorized FedEx, USPS, Pakket, and generic webhook normalization
- live tracking intelligence
- carrier-labelled evidence gate
- enterprise metrics
- customer-input financial scenarios
- general expected-vs-actual precision engine

All public empirical lanes currently packaged with the product have executed certificates. Carrier-brand-specific row-level accuracy remains locked behind the 5,000-completed-shipment evidence gate.
