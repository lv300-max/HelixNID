# HELIXNID Lane One-A — Real Amazon Last-Mile Benchmark

- Status: **PASS**
- Real training routes: **6,112**
- Real held-out evaluation routes: **3,052**
- Evaluation stop records, station included: **433,231**
- Synthetic rows used for claims: **0**
- Tuning routes: **500**, training-only holdout
- Selected weights: `(1.0, 1.0, 0.5, 0.15, 0.1)`

## Results against geographic nearest-neighbor

- Adjacent-edge recall: 0.248055 → **0.296437**, **19.50% improvement**
- Pair-order accuracy: 0.501406 → 0.484693, **3.33% lower**
- Spearman rank correlation: 0.004647 → -0.129466, lower
- Normalized position MAE: 0.321449 → 0.340333, **5.87% worse**

## Per-route win rates

- Adjacent-edge win rate: **73.07%**
- Pair-order win rate: **45.05%**
- Rank-correlation win rate: **38.73%**
- Position-error win rate: **40.69%**

## Evaluation file audit

- Published evaluation count: **3,072**
- Downloaded actual-sequence IDs: **3,052**
- Downloaded route-data IDs: **3,052**
- Usable paired IDs: **3,052**
- Published-count gap: **20**
- Unmatched IDs inside downloaded files: **0**

## Exact conclusion

HELIXNID materially improves local adjacent-edge recovery and wins that metric on 73.07% of routes. The current model does not improve global route ordering, rank correlation, or normalized position error. Those pressure points remain explicit optimization targets.

This is a real route-sequence benchmark. It is not a carrier ETA claim.
