#!/usr/bin/env python3
from __future__ import annotations
import json, shutil, subprocess, sys
from pathlib import Path

HERE=Path(__file__).resolve()
LANE=HERE.parents[3]
SOURCE=LANE/'src'/'helixnid_last_mile_benchmark_v2.py'
REPORTS=LANE/'reports'
OUT=HERE.parent

subprocess.run([sys.executable,str(SOURCE)],check=True)
for name in [
    'release_certificate.json','benchmark_result_table.csv','empirical_run_report.md',
    'data_validation_report.json','evaluation_intersection_audit.json',
    'dataset_source_ledger.md','artifact_hashes.csv'
]:
    src=REPORTS/name
    if src.exists(): shutil.copy2(src,OUT/name)
cert=json.loads((OUT/'release_certificate.json').read_text(encoding='utf-8'))
print(json.dumps(cert,indent=2))
