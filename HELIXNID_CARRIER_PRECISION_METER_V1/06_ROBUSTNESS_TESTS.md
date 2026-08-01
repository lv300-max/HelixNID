# Robustness Tests

Executable suite: `HELIXNID_EMPIRICAL_LANE_ONE/product_1_4/01_robustness/`.

Coverage:
- 50/50 chronological split
- 60/40 chronological split
- 70/30 chronological split
- 80/20 chronological split
- rolling-origin future blocks
- calendar-month holdouts
- stress segments

Primary output: `robustness_results.csv` plus `robustness_certificate.json`.

The final release workflow records the observed floor/median/high improvement after execution.
