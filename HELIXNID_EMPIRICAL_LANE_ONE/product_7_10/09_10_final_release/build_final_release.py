#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, shutil
from datetime import datetime, timezone
from pathlib import Path

HERE=Path(__file__).resolve()
LANE=HERE.parents[3]
REPO=LANE.parent
OUT=REPO/'HELIXNID_CARRIER_PRECISION_METER_V1'
CERTS=OUT/'certificates'
CERTS.mkdir(parents=True,exist_ok=True)

def readj(p):
    p=Path(p)
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None

def sha(p):
    h=hashlib.sha256();
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def status(x): return 'LOCKED' if x else 'PENDING_EXECUTION'

olist=readj(LANE/'reports_olist_eta'/'release_certificate.json')
p14=readj(LANE/'product_1_4'/'PRODUCT_1_4_CERTIFICATE.json')
p56=readj(LANE/'product_5_6'/'PRODUCT_5_6_BUILD_CERTIFICATE.json')
lade=readj(LANE/'product_7_10'/'07_external_replication'/'replication_certificate.json')
amazon=readj(LANE/'product_7_10'/'08_amazon_operational'/'release_certificate.json')

sources=[
 ('olist_real_eta',olist,LANE/'reports_olist_eta'/'release_certificate.json'),
 ('product_1_4',p14,LANE/'product_1_4'/'PRODUCT_1_4_CERTIFICATE.json'),
 ('product_5_6',p56,LANE/'product_5_6'/'PRODUCT_5_6_BUILD_CERTIFICATE.json'),
 ('lade_replication',lade,LANE/'product_7_10'/'07_external_replication'/'replication_certificate.json'),
 ('amazon_routes',amazon,LANE/'product_7_10'/'08_amazon_operational'/'release_certificate.json'),
]
for name,obj,path in sources:
    if path.exists(): shutil.copy2(path,CERTS/f'{name}.json')

locked_reduction = olist.get('eta_error_reduction_pct') if olist else None
real_orders = olist.get('valid_real_completed_orders') if olist else None
future_orders = olist.get('chronological_test_orders') if olist else None

files={
'00_README.md':f'''# HELIXNID Carrier Precision Meter V1

A delivery-promise correction and late-risk measurement product built on the existing HELIXNID evidence system.

## Product path

Shipment / tracking facts -> HELIXNID scoring engine -> corrected ETA + late risk -> API -> dashboard -> evidence certificate.

## Locked real evidence

- Olist completed-order evidence: **{real_orders if real_orders is not None else 'pending'}** real orders.
- Future chronological holdout: **{future_orders if future_orders is not None else 'pending'}** orders.
- ETA error reduction: **{locked_reduction:.2f}%** if locked_reduction is not None else **pending**.
- Synthetic rows used for empirical claims: **0**.

## Release components

1. Robustness suite
2. Ten-model baseline battle
3. Business-value conversion
4. Product scoring engine
5. FastAPI plug-in API
6. Live dashboard
7. Independent LaDe industry replication
8. Amazon route/stop-order benchmark
9. Executive evidence package
10. Master release certificate
''',
'01_PRODUCT.md':'''# Product

## Input

- shipment ID
- ship/purchase time
- carrier handoff time
- original promised ETA
- optional carrier/service/destination identifiers

## Output

- original ETA
- HELIXNID corrected ETA
- correction size
- late probability
- risk band
- confidence
- matched historical support
- warning window
- model/data evidence identifiers

The customer-facing product is the measurement layer. Internal HELIXNID evidence structures remain behind the interface.
''',
'02_HOW_IT_WORKS.md':'''# How It Works

1. Receive a shipment state at carrier handoff.
2. Convert known timing facts into locked historical buckets.
3. Find the strongest supported historical level.
4. Produce a delivery-date correction and late-risk estimate.
5. Return confidence and historical support count.
6. Record model/data certificate identity for replay.

The V1 Olist model does not learn FedEx/UPS/DHL brand effects because the Olist evidence does not expose carrier brand identity.
''',
'03_REAL_DATA_SOURCES.md':'''# Real Data Sources

## Olist
Real anonymized completed e-commerce orders. Contains customer-facing estimated delivery date and actual delivery timestamp. This is the primary V1 delivery-promise benchmark.

## LaDe-D
Real last-mile industry task-event data from Cainiao-AI. Used as an independent operational timing replication. It is not relabeled as a customer-promise ETA dataset.

## Amazon Last Mile Routing Research Challenge
Real historical Amazon driver routes. Used for route/stop-order precision on held-out evaluation routes.

Synthetic rows used for empirical claims: **0**.
''',
'04_EMPIRICAL_RESULTS.md':f'''# Empirical Results

## Olist delivery-promise benchmark

Status: **{status(olist)}**

''' + (f'''- Real completed orders: **{olist['valid_real_completed_orders']:,}**
- Train: **{olist['chronological_train_orders']:,}**
- Future test: **{olist['chronological_test_orders']:,}**
- Official MAE: **{olist['official_delivery_date_mae_days']:.3f} days**
- HELIXNID MAE: **{olist['helixnid_corrected_mae_days']:.3f} days**
- ETA error reduction: **{olist['eta_error_reduction_pct']:.2f}%**
- Late-risk ROC-AUC: **{olist['late_risk_roc_auc']:.4f}**
''' if olist else 'Execution certificate not present.\n') + f'''
## LaDe independent replication
Status: **{status(lade)}**

''' + (f'''- Valid real tasks: **{lade['valid_rows']:,}**
- Future test: **{lade['chronological_test_rows']:,}**
- Baseline timing MAE: **{lade['baseline_mae_minutes']:.3f} min**
- HELIXNID timing MAE: **{lade['helixnid_hierarchical_mae_minutes']:.3f} min**
- Relative reduction: **{lade['relative_mae_reduction_pct']:.2f}%**
''' if lade else 'Benchmark runner is packaged; certificate will be inserted after execution.\n') + f'''
## Amazon operational route benchmark
Status: **{status(amazon)}**

''' + (json.dumps(amazon.get('comparison'),indent=2) if amazon else 'Benchmark runner is packaged; certificate will be inserted after execution.') + '\n',
'05_BASELINE_LEADERBOARD.md':f'''# Baseline Leaderboard

Product 2 status: **{status(p14)}**.

The executable comparison includes official promise, global median, recent median, linear regression, ridge, random forest, extra trees, gradient boosting, XGBoost, and HELIXNID historical hierarchy.

Generated leaderboard: `HELIXNID_EMPIRICAL_LANE_ONE/product_1_4/02_baseline_battle/BENCHMARK_LEADERBOARD.csv`.
''',
'06_ROBUSTNESS_TESTS.md':f'''# Robustness Tests

Product 1 status: **{status(p14)}**.

The suite covers 50/50, 60/40, 70/30, and 80/20 chronological splits, rolling-origin future tests, calendar-month holdouts, and stress segments.

Generated evidence: `HELIXNID_EMPIRICAL_LANE_ONE/product_1_4/01_robustness/`.
''',
'07_BUSINESS_VALUE.md':'''# Business Value Measurements

The product converts measured rates into operational counts at 1,000 / 10,000 / 100,000 shipment scales.

Tracked values include:
- ETA error-days removed
- additional shipments inside +/-1 day
- additional shipments inside +/-2 days
- high-risk shipments flagged
- late shipments captured
- warning hours available

No dollar savings are claimed without buyer-specific cost inputs.
''',
'08_API_SPEC.md':'''# API

FastAPI implementation: `HELIXNID_EMPIRICAL_LANE_ONE/product_5_6/05_api/app.py`.

Endpoints:
- `POST /score-shipment`
- `POST /correct-eta`
- `POST /late-risk`
- `POST /batch-score`
- `POST /carrier-report`
- `POST /route-report`
- `GET /metrics`
- `GET /certificate`
- `GET /health`

Batch scoring supports up to 10,000 shipments per request.
''',
'09_DASHBOARD_SPEC.md':'''# Dashboard

Dashboard implementation: `HELIXNID_EMPIRICAL_LANE_ONE/product_5_6/06_dashboard/`.

Primary surfaces:
- shipments scored
- high risk count
- average correction
- corrected ETA
- late probability
- risk band
- confidence
- matched history
- warning window
- locked empirical proof
- recent scored shipments

The browser calls the API. Scoring logic is not duplicated in JavaScript.
''',
'10_INTEGRATION_SPEC.md':'''# Integration

## Minimum live connector mapping

Required:
- shipment_id
- ship_time or purchase_time
- carrier_handoff_time
- carrier_eta_time or promised_delivery_time

Optional:
- carrier
- service
- destination / destination_zip

Carrier/service fields are accepted now. Brand-specific corrections remain evidence-gated until carrier-labeled completed shipment history is connected.
''',
'11_REVIEWER_GUIDE.md':'''# Reviewer Guide

Check in this order:

1. `certificates/olist_real_eta.json` — primary real ETA benchmark.
2. `04_EMPIRICAL_RESULTS.md` — headline measurements and boundaries.
3. `05_BASELINE_LEADERBOARD.md` — competing models.
4. `06_ROBUSTNESS_TESTS.md` — time-split stability.
5. `08_API_SPEC.md` and `09_DASHBOARD_SPEC.md` — usable product surfaces.
6. `certificates/lade_replication.json` — independent operational replication when executed.
7. `certificates/amazon_routes.json` — route benchmark when executed.
8. `RELEASE_CERTIFICATE.json` — master release state and artifact hashes.

No synthetic empirical rows are used for claims.
''',
'12_EVIDENCE_LEDGER.md':f'''# Evidence Ledger

- Olist empirical certificate: **{status(olist)}**
- Product 1-4 certificate: **{status(p14)}**
- Product 5-6 certificate: **{status(p56)}**
- LaDe replication certificate: **{status(lade)}**
- Amazon route certificate: **{status(amazon)}**
- Synthetic empirical rows: **0**

The master certificate records which layers are locked versus awaiting external execution.
'''
}
for name,content in files.items(): (OUT/name).write_text(content,encoding='utf-8')

manifest=[]
for p in sorted(OUT.rglob('*')):
    if p.is_file() and p.name not in {'RELEASE_CERTIFICATE.json','ARTIFACT_HASHES.json'}:
        manifest.append({'path':str(p.relative_to(OUT)),'bytes':p.stat().st_size,'sha256':sha(p)})
(OUT/'ARTIFACT_HASHES.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')

all_locked=all(obj is not None for _,obj,_ in sources)
release={
 'certificate':'HELIXNID_CARRIER_PRECISION_METER_V1_RELEASE',
 'generated_utc':datetime.now(timezone.utc).isoformat(),
 'status':'PASS_ALL_LOCKED' if all_locked else 'PRODUCT_COMPLETE_WITH_EXECUTION_GATES',
 'product':'HELIXNID Carrier Precision Meter V1',
 'components_built':10,
 'synthetic_empirical_rows':0,
 'primary_eta_evidence':None if not olist else {
   'completed_orders':olist['valid_real_completed_orders'],'future_test_orders':olist['chronological_test_orders'],
   'official_mae_days':olist['official_delivery_date_mae_days'],'helixnid_mae_days':olist['helixnid_corrected_mae_days'],
   'eta_error_reduction_pct':olist['eta_error_reduction_pct']},
 'locks':{name:status(obj) for name,obj,_ in sources},
 'artifact_count':len(manifest),
 'artifact_hash_ledger':'ARTIFACT_HASHES.json',
 'claim_boundary':'Olist supports real delivery-promise correction. LaDe supports independent operational timing replication. Amazon supports route-sequence precision. Carrier-brand-specific ETA claims require carrier-labelled completed shipment evidence.'
}
(OUT/'RELEASE_CERTIFICATE.json').write_text(json.dumps(release,indent=2),encoding='utf-8')
print(json.dumps(release,indent=2))
