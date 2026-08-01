#!/usr/bin/env python3
"""Run HELIXNID Carrier Precision Product stages 1-4 and hash the outputs."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PRODUCT = ROOT / "product_1_4"


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def run(script, *args):
    cmd = [sys.executable, str(SRC / script), *args]
    print("RUN", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def main():
    run("robustness_suite.py")
    run("baseline_battle.py")
    run("business_value.py")
    run("carrier_precision_engine.py", "train")

    expected = [
        PRODUCT / "01_robustness" / "robustness_certificate.json",
        PRODUCT / "02_baseline_battle" / "baseline_battle_certificate.json",
        PRODUCT / "03_business_value" / "business_value_certificate.json",
        PRODUCT / "04_scoring_engine" / "carrier_precision_model_v1.json",
    ]
    missing = [str(p.relative_to(ROOT)) for p in expected if not p.exists()]
    artifacts = {}
    for path in sorted(PRODUCT.rglob("*")):
        if path.is_file():
            artifacts[str(path.relative_to(ROOT))] = {"bytes": path.stat().st_size, "sha256": sha256(path)}

    cert = {
        "certificate": "HELIXNID_CARRIER_PRECISION_PRODUCT_1_4_V1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if not missing else "INCOMPLETE",
        "components": {
            "1_robustness_attack": str(expected[0].relative_to(ROOT)),
            "2_ten_model_baseline_battle": str(expected[1].relative_to(ROOT)),
            "3_business_value_conversion": str(expected[2].relative_to(ROOT)),
            "4_product_scoring_engine": str(expected[3].relative_to(ROOT)),
        },
        "missing": missing,
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }
    PRODUCT.mkdir(parents=True, exist_ok=True)
    (PRODUCT / "PRODUCT_1_4_CERTIFICATE.json").write_text(json.dumps(cert, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in cert.items() if k != "artifacts"}, indent=2))


if __name__ == "__main__":
    main()
