# HELIXNID Empirical Lane One

## Product lane

**HELIXNID Carrier Precision Meter**

## Empirical split

- **Lane One-A — Route / stop-order precision:** executable now on real public Amazon operational data.
- **Lane One-B — Carrier ETA correction:** kept as the product interface, but no ETA-improvement claim is issued until a real public dataset contains both promised carrier ETA and actual parcel delivery time.

## Real source

2021 Amazon Last Mile Routing Research Challenge dataset.

- 6,112 historical training routes.
- 3,072 held-out historical evaluation routes.
- Routes were performed by Amazon drivers in 2018 in five U.S. metropolitan areas.
- Synthetic rows used for the empirical benchmark: 0.

## What the benchmark measures

HELIXNID is compared with a geographic nearest-neighbor baseline on the same held-out routes.

Outputs:

- adjacent-edge recall
- pair-order accuracy
- Spearman route-rank correlation
- normalized stop-position MAE
- per-route HELIXNID win rates
- dataset acquisition hashes
- validation certificate
- artifact hash ledger

## Runner

`src/helixnid_last_mile_benchmark.py`

The runner acquires the four official public Amazon files itself, verifies exact byte sizes, validates route/stop structure, tunes only on training data, evaluates all 3,072 held-out routes, and writes the `reports/` package.
