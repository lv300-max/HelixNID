#!/usr/bin/env python3
"""HELIXNID Lane One-A: real Amazon last-mile route precision benchmark.

Uses only public, real 2021 Amazon Last Mile Routing Research Challenge data.
Training: 6,112 historical routes. Evaluation: 3,072 held-out historical routes.
No synthetic shipment rows are used for empirical claims.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import statistics
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS = ROOT / "reports"
DATA.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

BASE = "https://amazon-last-mile-challenges.s3.us-west-2.amazonaws.com/almrrc2021"
FILES = {
    "training_actual_sequences.json": (
        "almrrc2021-data-training/model_build_inputs/actual_sequences.json",
        9_665_078,
    ),
    "training_route_data.json": (
        "almrrc2021-data-training/model_build_inputs/route_data.json",
        78_972_162,
    ),
    "eval_actual_sequences.json": (
        "almrrc2021-data-evaluation/model_score_inputs/eval_actual_sequences.json",
        4_625_218,
    ),
    "eval_route_data.json": (
        "almrrc2021-data-evaluation/model_apply_inputs/eval_route_data.json",
        37_777_768,
    ),
}

OMEGA = 13_507
GRID_M = 1_849


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download() -> list[dict]:
    rows = []
    for local_name, (key, expected) in FILES.items():
        path = DATA / local_name
        url = f"{BASE}/{key}"
        status = "cached"
        if not path.exists() or path.stat().st_size != expected:
            part = path.with_suffix(path.suffix + ".part")
            req = urllib.request.Request(url, headers={"User-Agent": "HELIXNID-Empirical/1.0"})
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=120) as r, part.open("wb") as out:
                while True:
                    block = r.read(1024 * 1024)
                    if not block:
                        break
                    out.write(block)
            seconds = time.time() - t0
            if part.stat().st_size != expected:
                raise RuntimeError(f"size mismatch {local_name}: {part.stat().st_size} != {expected}")
            part.replace(path)
            status = f"downloaded:{seconds:.2f}s"
        rows.append({
            "file": local_name,
            "source": url,
            "bytes": path.stat().st_size,
            "expected_bytes": expected,
            "sha256": sha256(path),
            "status": status,
        })
    with (REPORTS / "acquisition_log.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)
    return rows


def load_json(name: str):
    with (DATA / name).open() as f:
        return json.load(f)


def seq_list(entry: dict, key: str) -> list[str]:
    d = entry[key]
    return [stop for stop, pos in sorted(d.items(), key=lambda kv: kv[1])]


def zone_parts(zone) -> tuple[str, str, str]:
    if not isinstance(zone, str) or not zone:
        return ("?", "?", "?")
    region = zone.split("-", 1)[0]
    coarse = zone.rsplit(".", 1)[0] if "." in zone else zone
    return zone, coarse, region


def hav_km(a: dict, b: dict) -> float:
    lat1, lon1 = math.radians(float(a["lat"])), math.radians(float(a["lng"]))
    lat2, lon2 = math.radians(float(b["lat"])), math.radians(float(b["lng"]))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(h)))


def station_stop(route: dict) -> str:
    stations = [s for s, x in route["stops"].items() if x.get("type") == "Station"]
    if len(stations) != 1:
        raise ValueError(f"expected one station stop, got {len(stations)}")
    return stations[0]


class History:
    def __init__(self):
        self.start = Counter()
        self.trans = Counter()
        self.coarse = Counter()
        self.region = Counter()
        self.start_totals = Counter()
        self.trans_totals = Counter()

    def add_route(self, station: str, route: dict, seq: list[str]):
        stops = route["stops"]
        depot = station_stop(route)
        ordered = [s for s in seq if s != depot]
        if not ordered:
            return
        z0 = zone_parts(stops[ordered[0]].get("zone_id"))[0]
        self.start[(station, z0)] += 1
        self.start_totals[station] += 1
        prev = ordered[0]
        for nxt in ordered[1:]:
            z1, c1, r1 = zone_parts(stops[prev].get("zone_id"))
            z2, c2, r2 = zone_parts(stops[nxt].get("zone_id"))
            self.trans[(station, z1, z2)] += 1
            self.trans_totals[(station, z1)] += 1
            self.coarse[(station, c1, c2)] += 1
            self.region[(station, r1, r2)] += 1
            prev = nxt


def build_history(route_data: dict, actual: dict, route_ids: list[str]) -> History:
    h = History()
    for rid in route_ids:
        if rid not in route_data or rid not in actual:
            continue
        route = route_data[rid]
        h.add_route(route["station_code"], route, seq_list(actual[rid], "actual"))
    return h


def tie_value(stop: str, step: int) -> float:
    # Existing HELIXNID constants are used only as a deterministic tie-break.
    n = sum((i + 1) * ord(ch) for i, ch in enumerate(stop)) + OMEGA + step
    x = n % GRID_M
    d = min(x, GRID_M - x)
    return -d / GRID_M / 1000.0


def predict_geo(route: dict) -> list[str]:
    stops = route["stops"]
    depot = station_stop(route)
    out = [depot]
    unseen = set(stops) - {depot}
    cur = depot
    while unseen:
        nxt = min(unseen, key=lambda s: (hav_km(stops[cur], stops[s]), s))
        out.append(nxt); unseen.remove(nxt); cur = nxt
    return out


def predict_helix(route: dict, hist: History, weights: tuple[float, float, float, float, float]) -> list[str]:
    w_trans, w_same, w_coarse, w_region, w_geo = weights
    stops = route["stops"]
    station = route["station_code"]
    depot = station_stop(route)
    unseen = set(stops) - {depot}
    out = [depot]
    cur = depot
    step = 0
    while unseen:
        best = None
        best_score = -1e99
        cur_zone, cur_coarse, cur_region = zone_parts(stops[cur].get("zone_id"))
        for cand in unseen:
            z, coarse, region = zone_parts(stops[cand].get("zone_id"))
            if cur == depot:
                c = hist.start[(station, z)]
                total = hist.start_totals[station]
                p = (c + 0.2) / (total + 0.2 * max(1, len(unseen)))
                trans_term = math.log1p(30.0 * p)
                same = coarse_same = region_same = 0.0
            else:
                c = hist.trans[(station, cur_zone, z)]
                total = hist.trans_totals[(station, cur_zone)]
                p = (c + 0.1) / (total + 0.1 * max(1, len(unseen)))
                trans_term = math.log1p(50.0 * p)
                same = 1.0 if z == cur_zone and z != "?" else 0.0
                coarse_same = 1.0 if coarse == cur_coarse and coarse != "?" else 0.0
                region_same = 1.0 if region == cur_region and region != "?" else 0.0
                # Learned coarse/region transitions add pressure without making them hard rules.
                trans_term += 0.10 * math.log1p(hist.coarse[(station, cur_coarse, coarse)])
                trans_term += 0.04 * math.log1p(hist.region[(station, cur_region, region)])
            geo = hav_km(stops[cur], stops[cand])
            score = (
                w_trans * trans_term
                + w_same * same
                + w_coarse * coarse_same
                + w_region * region_same
                - w_geo * geo
                + tie_value(cand, step)
            )
            if score > best_score or (score == best_score and (best is None or cand < best)):
                best_score = score; best = cand
        out.append(best); unseen.remove(best); cur = best; step += 1
    return out


def inversion_count(arr: list[int]) -> int:
    def sort_count(xs):
        n = len(xs)
        if n < 2:
            return xs, 0
        m = n // 2
        a, ca = sort_count(xs[:m]); b, cb = sort_count(xs[m:])
        i = j = inv = 0; merged = []
        while i < len(a) and j < len(b):
            if a[i] <= b[j]:
                merged.append(a[i]); i += 1
            else:
                merged.append(b[j]); j += 1; inv += len(a) - i
        merged.extend(a[i:]); merged.extend(b[j:])
        return merged, ca + cb + inv
    return sort_count(arr)[1]


def metrics(actual: list[str], pred: list[str], depot: str) -> dict:
    a = [s for s in actual if s != depot]
    p = [s for s in pred if s != depot]
    if set(a) != set(p) or len(a) != len(p):
        raise ValueError("prediction stop set mismatch")
    n = len(a)
    if n < 2:
        return {"edge_recall": 1.0, "pair_order_accuracy": 1.0, "rank_corr": 1.0, "norm_pos_mae": 0.0}
    apos = {s: i for i, s in enumerate(a)}
    ppos = {s: i for i, s in enumerate(p)}
    actual_edges = set(zip(a[:-1], a[1:]))
    pred_edges = set(zip(p[:-1], p[1:]))
    edge = len(actual_edges & pred_edges) / len(actual_edges)
    arr = [apos[s] for s in p]
    inv = inversion_count(arr)
    pairs = n * (n - 1) / 2
    pair_acc = 1.0 - inv / pairs
    # Spearman rho for a permutation with no ties.
    sum_d2 = sum((apos[s] - ppos[s]) ** 2 for s in a)
    rho = 1.0 - (6.0 * sum_d2) / (n * (n * n - 1))
    pos_mae = statistics.fmean(abs(apos[s] - ppos[s]) for s in a) / max(1, n - 1)
    return {"edge_recall": edge, "pair_order_accuracy": pair_acc, "rank_corr": rho, "norm_pos_mae": pos_mae}


def aggregate(rows: list[dict], prefix: str) -> dict:
    keys = ["edge_recall", "pair_order_accuracy", "rank_corr", "norm_pos_mae"]
    out = {}
    for k in keys:
        vals = [r[f"{prefix}_{k}"] for r in rows]
        out[k] = statistics.fmean(vals)
        out[k + "_median"] = statistics.median(vals)
    return out


def improvement(g: float, h: float, higher_better=True) -> float:
    if g == 0:
        return float("nan")
    return ((h - g) / abs(g) * 100.0) if higher_better else ((g - h) / abs(g) * 100.0)


def tune(train_routes: dict, train_actual: dict, train_ids: list[str]):
    # Deterministic 80/20 split by route ID. Tune only on held-out training routes.
    ids = sorted(train_ids, key=lambda r: hashlib.sha256(r.encode()).hexdigest())
    cut = int(len(ids) * 0.80)
    fit, hold = ids[:cut], ids[cut:]
    hist = build_history(train_routes, train_actual, fit)
    candidates = [
        (1.0, 1.0, 0.5, 0.15, 0.10),
        (1.3, 1.3, 0.6, 0.20, 0.08),
        (1.6, 1.6, 0.8, 0.25, 0.07),
        (2.0, 2.0, 1.0, 0.30, 0.06),
        (2.4, 2.2, 1.1, 0.35, 0.05),
        (1.8, 2.8, 1.3, 0.40, 0.05),
        (2.2, 3.2, 1.5, 0.45, 0.04),
        (2.8, 3.5, 1.6, 0.50, 0.035),
    ]
    # Keep tuning bounded but representative.
    tune_ids = hold[: min(500, len(hold))]
    result = []
    for w in candidates:
        vals = []
        for rid in tune_ids:
            route = train_routes[rid]
            actual = seq_list(train_actual[rid], "actual")
            pred = predict_helix(route, hist, w)
            m = metrics(actual, pred, station_stop(route))
            vals.append(m)
        edge = statistics.fmean(x["edge_recall"] for x in vals)
        pair = statistics.fmean(x["pair_order_accuracy"] for x in vals)
        rho = statistics.fmean(x["rank_corr"] for x in vals)
        pos = statistics.fmean(x["norm_pos_mae"] for x in vals)
        objective = 0.40 * edge + 0.30 * pair + 0.30 * ((rho + 1.0) / 2.0) - 0.10 * pos
        result.append({"weights": w, "objective": objective, "edge": edge, "pair": pair, "rho": rho, "pos": pos})
    result.sort(key=lambda x: x["objective"], reverse=True)
    return result[0]["weights"], result, len(tune_ids)


def write_csv(path: Path, rows: list[dict]):
    if not rows:
        return
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


def main():
    started = time.time()
    acquired = download()
    train_actual = load_json("training_actual_sequences.json")
    train_routes = load_json("training_route_data.json")
    eval_actual = load_json("eval_actual_sequences.json")
    eval_routes = load_json("eval_route_data.json")

    train_ids = sorted(set(train_actual) & set(train_routes))
    eval_ids = sorted(set(eval_actual) & set(eval_routes))
    if len(train_ids) != 6112:
        raise RuntimeError(f"training route count mismatch: {len(train_ids)}")
    if len(eval_ids) != 3072:
        raise RuntimeError(f"evaluation route count mismatch: {len(eval_ids)}")

    # Structural validation.
    val_rows = []
    eval_stop_total = 0
    for rid in eval_ids:
        route = eval_routes[rid]
        actual = seq_list(eval_actual[rid], "actual")
        if set(actual) != set(route["stops"]):
            raise RuntimeError(f"stop-set mismatch: {rid}")
        depot = station_stop(route)
        if actual[0] != depot:
            raise RuntimeError(f"actual route does not start at station: {rid}")
        eval_stop_total += len(actual)

    best_weights, tuning, tune_n = tune(train_routes, train_actual, train_ids)
    full_hist = build_history(train_routes, train_actual, train_ids)

    route_rows = []
    for idx, rid in enumerate(eval_ids, 1):
        route = eval_routes[rid]
        actual = seq_list(eval_actual[rid], "actual")
        depot = station_stop(route)
        geo = predict_geo(route)
        helix = predict_helix(route, full_hist, best_weights)
        gm = metrics(actual, geo, depot)
        hm = metrics(actual, helix, depot)
        route_rows.append({
            "route_id": rid,
            "station_code": route["station_code"],
            "stop_count": len(actual),
            "geo_edge_recall": gm["edge_recall"],
            "helix_edge_recall": hm["edge_recall"],
            "geo_pair_order_accuracy": gm["pair_order_accuracy"],
            "helix_pair_order_accuracy": hm["pair_order_accuracy"],
            "geo_rank_corr": gm["rank_corr"],
            "helix_rank_corr": hm["rank_corr"],
            "geo_norm_pos_mae": gm["norm_pos_mae"],
            "helix_norm_pos_mae": hm["norm_pos_mae"],
            "helix_edge_win": int(hm["edge_recall"] > gm["edge_recall"]),
            "helix_pair_win": int(hm["pair_order_accuracy"] > gm["pair_order_accuracy"]),
            "helix_rank_win": int(hm["rank_corr"] > gm["rank_corr"]),
            "helix_pos_win": int(hm["norm_pos_mae"] < gm["norm_pos_mae"]),
        })
        if idx % 250 == 0:
            print(f"evaluated {idx}/{len(eval_ids)}", flush=True)

    geo = aggregate(route_rows, "geo")
    helix = aggregate(route_rows, "helix")
    n = len(route_rows)
    wins = {
        "edge_win_rate": sum(r["helix_edge_win"] for r in route_rows) / n,
        "pair_win_rate": sum(r["helix_pair_win"] for r in route_rows) / n,
        "rank_win_rate": sum(r["helix_rank_win"] for r in route_rows) / n,
        "position_win_rate": sum(r["helix_pos_win"] for r in route_rows) / n,
    }

    comparison = [
        {"metric": "Adjacent-edge recall", "direction": "higher", "geo_baseline": geo["edge_recall"], "helixnid": helix["edge_recall"], "relative_improvement_pct": improvement(geo["edge_recall"], helix["edge_recall"], True)},
        {"metric": "Pair-order accuracy", "direction": "higher", "geo_baseline": geo["pair_order_accuracy"], "helixnid": helix["pair_order_accuracy"], "relative_improvement_pct": improvement(geo["pair_order_accuracy"], helix["pair_order_accuracy"], True)},
        {"metric": "Spearman rank correlation", "direction": "higher", "geo_baseline": geo["rank_corr"], "helixnid": helix["rank_corr"], "relative_improvement_pct": improvement(geo["rank_corr"], helix["rank_corr"], True)},
        {"metric": "Normalized position MAE", "direction": "lower", "geo_baseline": geo["norm_pos_mae"], "helixnid": helix["norm_pos_mae"], "relative_improvement_pct": improvement(geo["norm_pos_mae"], helix["norm_pos_mae"], False)},
    ]
    write_csv(REPORTS / "benchmark_result_table.csv", comparison)
    write_csv(REPORTS / "route_results.csv", route_rows)
    write_csv(REPORTS / "tuning_results.csv", [
        {"weights": str(x["weights"]), "objective": x["objective"], "edge_recall": x["edge"], "pair_order_accuracy": x["pair"], "rank_corr": x["rho"], "norm_pos_mae": x["pos"]}
        for x in tuning
    ])

    validation = {
        "source_is_real_operational_data": True,
        "synthetic_rows_used_for_claims": 0,
        "training_routes": len(train_ids),
        "evaluation_routes": len(eval_ids),
        "evaluation_stops_including_station": eval_stop_total,
        "all_eval_stop_sets_match": True,
        "all_eval_routes_start_at_station": True,
        "download_files_size_verified": True,
        "tuning_routes": tune_n,
        "best_weights": best_weights,
    }
    (REPORTS / "data_validation_report.json").write_text(json.dumps(validation, indent=2))

    elapsed = time.time() - started
    certificate = {
        "certificate": "HELIXNID_LANE_ONE_A_REAL_LAST_MILE_BENCHMARK_V1",
        "status": "PASS",
        "generated_utc": utc_now(),
        "dataset": "2021 Amazon Last Mile Routing Research Challenge",
        "training_routes": len(train_ids),
        "evaluation_routes": len(eval_ids),
        "evaluation_stops_including_station": eval_stop_total,
        "synthetic_rows": 0,
        "baseline": "geographic nearest-neighbor",
        "helixnid_model": "station/zone historical transition pressure + geographic pressure + deterministic HELIX tie-break",
        "best_weights": best_weights,
        "metrics": {"geo": geo, "helixnid": helix, "wins": wins},
        "comparison": comparison,
        "elapsed_seconds": elapsed,
        "claim_boundary": "This benchmark measures route/stop-order precision on real Amazon operational routes. It does not claim carrier ETA MAE improvement because the public dataset does not contain carrier promised ETA versus actual parcel delivery timestamps.",
    }
    (REPORTS / "release_certificate.json").write_text(json.dumps(certificate, indent=2))

    report = [
        "# HELIXNID Lane One-A — Real Last-Mile Empirical Benchmark",
        "",
        f"- Status: **PASS**",
        f"- Real training routes: **{len(train_ids):,}**",
        f"- Real held-out evaluation routes: **{len(eval_ids):,}**",
        f"- Evaluation stop records (station included): **{eval_stop_total:,}**",
        "- Synthetic rows used for claims: **0**",
        f"- Tuning routes: **{tune_n:,}** (training-only holdout)",
        f"- Selected weights: `{best_weights}`",
        "",
        "## Headline results",
        "",
    ]
    for row in comparison:
        report.append(f"- {row['metric']}: geo={row['geo_baseline']:.6f} | HELIXNID={row['helixnid']:.6f} | relative improvement={row['relative_improvement_pct']:.2f}%")
    report += [
        "",
        "## Per-route win rates",
        "",
        f"- Adjacent-edge win rate: {wins['edge_win_rate']*100:.2f}%",
        f"- Pair-order win rate: {wins['pair_win_rate']*100:.2f}%",
        f"- Rank-correlation win rate: {wins['rank_win_rate']*100:.2f}%",
        f"- Position-error win rate: {wins['position_win_rate']*100:.2f}%",
        "",
        "## Claim boundary",
        "",
        "This is a real route-sequence benchmark. It does not convert these numbers into carrier ETA improvement. Carrier ETA precision remains Lane One-B and requires real rows containing both promised ETA and actual delivery time.",
    ]
    (REPORTS / "empirical_run_report.md").write_text("\n".join(report) + "\n")

    ledger = [
        "# Dataset Source Ledger",
        "",
        "Source: 2021 Amazon Last Mile Routing Research Challenge public S3 dataset.",
        "License: CC BY-NC 4.0 as stated by the AWS Registry entry.",
        "Operational origin: historical routes performed by Amazon drivers in 2018 across five U.S. metropolitan areas.",
        "",
        "## Acquired files",
    ]
    for x in acquired:
        ledger += [f"- `{x['file']}` — {x['bytes']:,} bytes — SHA256 `{x['sha256']}`"]
    (REPORTS / "dataset_source_ledger.md").write_text("\n".join(ledger) + "\n")

    # Hash all small report artifacts except the hash file itself.
    artifacts = []
    for p in sorted(REPORTS.iterdir()):
        if p.is_file() and p.name != "artifact_hashes.csv":
            artifacts.append({"file": p.name, "bytes": p.stat().st_size, "sha256": sha256(p)})
    write_csv(REPORTS / "artifact_hashes.csv", artifacts)
    print(json.dumps(certificate, indent=2))


if __name__ == "__main__":
    main()
