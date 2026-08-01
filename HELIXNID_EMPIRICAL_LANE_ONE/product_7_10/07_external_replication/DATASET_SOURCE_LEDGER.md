# Product 7 — Independent Real Dataset Replication

Source: **LaDe — The First Comprehensive Last-mile Delivery Dataset from Industry**.

- Publisher: Cainiao-AI.
- Public host: Hugging Face `Cainiao-AI/LaDe`.
- License: Apache-2.0.
- Scale stated by the dataset authors: about **10.677 million packages**, **21,000 couriers**, **6 months** of real-world operations.
- Delivery files cover Shanghai, Hangzhou, Chongqing, Jilin, and Yantai.
- V1 replication slice: `delivery_jl.csv`.
- Empirical rows: real delivery tasks only.
- Synthetic empirical rows: **0**.

## Replication task

Predict the elapsed time from courier task acceptance to completed delivery using information available at acceptance.

This intentionally does **not** relabel LaDe as a carrier ETA dataset. LaDe-D contains actual task-event timing, but no customer-facing promised delivery ETA. The replication therefore tests independent real-world delivery-timing generalization.
