# HELIXNID Carrier Precision Meter — Real Olist Run

- Status: **PASS**
- Raw orders: **99,441**
- Valid real completed deliveries: **96,281**
- Historical training orders: **67,396**
- Held-out future test orders: **28,885**
- Synthetic rows: **0**

## Delivery-promise precision

- Official estimate MAE: **13.446 days**
- Global historical correction MAE: **7.104 days**
- HELIXNID corrected MAE: **4.116 days**
- HELIXNID error reduction: **69.39%**
- Paired bootstrap 95% range: **68.97% to 69.77%**
- Official median absolute error: **13.0 days**
- HELIXNID median absolute error: **3.0 days**
- Official within ±1 day: **4.54%**
- HELIXNID within ±1 day: **30.18%**
- Official within ±2 days: **7.27%**
- HELIXNID within ±2 days: **45.41%**

## Late-risk triage at carrier handoff

- Future test late rate: **4.32%**
- Risk ROC-AUC: **0.7283**
- Risk average precision: **0.3174**
- Top 5% risk bucket captures **33.28%** of late deliveries at **28.74%** precision.
- Top 10% risk bucket captures **42.90%** of late deliveries at **18.52%** precision.
- Top 10% precision lift over base late rate: **4.29x**.
- Top 10% median warning lead: **127.13 hours**.

## Boundary

Olist supplies a customer-facing estimated delivery **date** and actual delivery timestamp. Carrier brand identity is not present, so these are real delivery-promise correction results rather than FedEx/UPS brand claims.
