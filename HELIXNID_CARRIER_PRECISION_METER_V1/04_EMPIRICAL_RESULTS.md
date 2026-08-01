# Empirical Results

## Primary locked Olist result

- Real completed orders: **96,281**
- Chronological train: **67,396**
- Future test: **28,885**
- Official delivery-date MAE: **13.446 days**
- HELIXNID corrected MAE: **4.116 days**
- ETA error reduction: **69.39%**
- 95% paired bootstrap range: **68.97%–69.77%**
- Official within ±1 day: **4.54%**
- HELIXNID within ±1 day: **30.18%**
- Official within ±2 days: **7.27%**
- HELIXNID within ±2 days: **45.41%**
- Late-risk ROC-AUC: **0.7283**
- Synthetic empirical rows: **0**

## Independent and operational evidence

- LaDe-D runner: built for independent real-industry accept-to-delivery timing replication.
- Amazon runner: built for 3,072 held-out real route-sequence evaluations.

Their generated certificates are inserted by the final release workflow and are not replaced with invented numbers before execution.
