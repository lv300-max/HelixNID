# HELIXNID Carrier Precision Meter V1 — Evidence Leaderboard

## Locked real evidence

| Lane | Real evaluation | Result | State |
|---|---:|---|---|
| Olist delivery-promise correction | 28,885 future orders | 13.446 → 4.116 days MAE; **69.39% reduction** | LOCKED |
| Robustness attack | 17 normal future holdouts + 6 stress slices | normal-holdout floor **25.72%**, median **63.33%**, max **74.95%** | LOCKED |
| 10-model battle | 28,885 future orders | HELIXNID **#3/10**, 4.116 d; XGBoost #1 at 3.854 d | LOCKED |
| Historical replay | 28,885 future shipments | **24,590 improved**, 269,503 absolute error-days removed | LOCKED |

## Documented pressure points

- `late_only` stress slice: HELIXNID 14.272 d MAE vs official 7.158 d, **-99.38%** relative change. This is retained as a failure region.
- Gap to XGBoost on the fixed future holdout: **0.263 day MAE**.

## External operational lanes

| Lane | Public source | State | Boundary |
|---|---|---|---|
| LaDe-D Jilin | Cainiao-AI LaDe | runner built; acquisition execution gate | accept-to-delivery timing, not customer promise ETA |
| Amazon last-mile | 2021 Amazon Last Mile Routing Research Challenge | runner built; acquisition execution gate | route-order precision, not customer promise ETA |

The external lanes do not change the locked Olist number until their own generated certificates exist.
