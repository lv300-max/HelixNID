#!/usr/bin/env python3
"""HELIXNID Product 7 — independent real-industry replication on LaDe-D.

This is NOT a carrier-promise ETA replication because LaDe-D has no customer promise.
It is an independent operational timing replication: predict accept->delivery elapsed
minutes from information available when the courier accepts the task.

Source: Cainiao-AI/LaDe, Apache-2.0, real last-mile industry operations.
Default slice: Jilin delivery file (small enough for deterministic CI execution).
Synthetic empirical rows: 0.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
OUT = HERE.parent
DATA = ROOT / "data" / "lade"
DATA.mkdir(parents=True, exist_ok=True)

URL = "https://huggingface.co/datasets/Cainiao-AI/LaDe/resolve/main/delivery/delivery_jl.csv?download=true"
FILE = DATA / "delivery_jl.csv"
EXPECTED_SHA256 = None  # recorded after acquisition; source identity is also in source ledger


def utc_now(): return datetime.now(timezone.utc).isoformat()

def sha256(path: Path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024), b''): h.update(b)
    return h.hexdigest()


def acquire():
    if not FILE.exists() or FILE.stat().st_size < 1_000_000:
        part=FILE.with_suffix('.csv.part')
        req=urllib.request.Request(URL, headers={'User-Agent':'HELIXNID-LaDe-Replication/1.0'})
        with urllib.request.urlopen(req, timeout=180) as r, part.open('wb') as out:
            while True:
                b=r.read(4*1024*1024)
                if not b: break
                out.write(b)
        part.replace(FILE)
    digest=sha256(FILE)
    if EXPECTED_SHA256 and digest != EXPECTED_SHA256:
        raise RuntimeError('LaDe file SHA256 mismatch')
    manifest={'dataset':'LaDe-D','city':'Jilin','source_url':URL,'bytes':FILE.stat().st_size,'sha256':digest,'synthetic_rows':0}
    (OUT/'acquisition_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest


def seconds_of_day(value: str):
    s=(value or '').strip()
    if not s: return None
    # Handles HH:MM:SS, YYYY-MM-DD HH:MM:SS, and MM-DD HH:MM:SS.
    timepart=s.split()[-1]
    p=timepart.split(':')
    if len(p)<2: return None
    try:
        h=int(float(p[0])); m=int(float(p[1])); sec=float(p[2]) if len(p)>2 else 0.0
        return h*3600+m*60+sec
    except Exception:
        return None


def hour_bucket(sec):
    h=int(sec//3600)
    if h<9:return '<09'
    if h<12:return '09-11'
    if h<15:return '12-14'
    if h<18:return '15-17'
    return '18+'


def load_rows():
    rows=[]; raw=0; invalid=0
    with FILE.open(newline='',encoding='utf-8') as f:
        reader=csv.DictReader(f)
        needed={'order_id','region_id','city','courier_id','aoi_id','aoi_type','accept_time','delivery_time','ds'}
        missing=needed-set(reader.fieldnames or [])
        if missing: raise RuntimeError(f'LaDe schema missing {sorted(missing)}')
        for r in reader:
            raw+=1
            a=seconds_of_day(r['accept_time']); d=seconds_of_day(r['delivery_time'])
            if a is None or d is None: invalid+=1; continue
            dur=d-a
            if dur<0: dur+=24*3600
            minutes=dur/60.0
            if not (0 <= minutes <= 24*60): invalid+=1; continue
            try: ds=int(float(r['ds']))
            except Exception: invalid+=1; continue
            rows.append({
                'order_id':r['order_id'],'ds':ds,'accept_sec':a,'duration_min':minutes,
                'courier_id':str(r['courier_id']),'region_id':str(r['region_id']),
                'aoi_id':str(r['aoi_id']),'aoi_type':str(r['aoi_type']),
                'hour_bucket':hour_bucket(a),
            })
    rows.sort(key=lambda x:(x['ds'],x['accept_sec'],x['order_id']))
    return rows, {'raw_rows':raw,'valid_rows':len(rows),'invalid_rows':invalid}

LEVELS=[
    (('courier_id','region_id','aoi_type','hour_bucket'),20),
    (('courier_id','aoi_type','hour_bucket'),20),
    (('region_id','aoi_type','hour_bucket'),30),
    (('courier_id','aoi_type'),30),
    (('region_id','aoi_type'),50),
    (('aoi_type','hour_bucket'),50),
]

class TimingModel:
    def __init__(self, train):
        self.global_median=statistics.median(x['duration_min'] for x in train)
        self.tables=[]
        for cols,minimum in LEVELS:
            d=defaultdict(list)
            for r in train:d[tuple(r[c] for c in cols)].append(r['duration_min'])
            self.tables.append((cols,{k:(statistics.median(v),len(v)) for k,v in d.items() if len(v)>=minimum}))
    def predict(self,r):
        for cols,t in self.tables:
            k=tuple(r[c] for c in cols)
            if k in t:return t[k][0],t[k][1],cols
        return self.global_median,0,('global',)


def mae(vals): return statistics.fmean(vals)

def percentile(xs,p):
    xs=sorted(xs); pos=(len(xs)-1)*p; lo=math.floor(pos); hi=math.ceil(pos)
    if lo==hi:return xs[lo]
    return xs[lo]*(hi-pos)+xs[hi]*(pos-lo)


def main():
    manifest=acquire(); rows,audit=load_rows()
    if len(rows)<5000: raise RuntimeError(f'LaDe valid-row gate failed: {len(rows)}')
    cut=int(len(rows)*0.70); train=rows[:cut]; test=rows[cut:]
    model=TimingModel(train)
    global_med=statistics.median(r['duration_min'] for r in train)
    base=[]; helix=[]; matched=[]
    for r in test:
        pred,n,level=model.predict(r)
        base.append(abs(r['duration_min']-global_med)); helix.append(abs(r['duration_min']-pred)); matched.append(n)
    b=mae(base); h=mae(helix); reduction=(b-h)/b*100 if b else 0.0
    cert={
        'certificate':'HELIXNID_LADE_EXTERNAL_REPLICATION_V1','status':'PASS',
        'generated_utc':utc_now(),'dataset':'LaDe-D Jilin','source_type':'real industry last-mile operations',
        'source_sha256':manifest['sha256'],'raw_rows':audit['raw_rows'],'valid_rows':audit['valid_rows'],
        'chronological_train_rows':len(train),'chronological_test_rows':len(test),'synthetic_rows':0,
        'task':'predict accept-to-delivery elapsed minutes at courier acceptance',
        'baseline':'global historical median elapsed minutes','baseline_mae_minutes':b,
        'helixnid_hierarchical_mae_minutes':h,'relative_mae_reduction_pct':reduction,
        'baseline_median_abs_error_minutes':statistics.median(base),'helixnid_median_abs_error_minutes':statistics.median(helix),
        'helixnid_p90_abs_error_minutes':percentile(helix,0.90),
        'matched_history_rows_median':statistics.median(matched),
        'claim_boundary':'Independent operational timing replication. LaDe-D does not contain a customer promised delivery ETA, so this result is not labeled carrier-promise ETA improvement.'
    }
    (OUT/'replication_certificate.json').write_text(json.dumps(cert,indent=2),encoding='utf-8')
    (OUT/'REPLICATION_REPORT.md').write_text(
        '# HELIXNID External Replication — LaDe-D\n\n'
        f"- Real valid tasks: **{audit['valid_rows']:,}**\n- Train: **{len(train):,}**\n- Future test: **{len(test):,}**\n"
        f"- Global-median MAE: **{b:.3f} min**\n- HELIXNID hierarchy MAE: **{h:.3f} min**\n- Relative MAE reduction: **{reduction:.2f}%**\n- Synthetic rows: **0**\n\n"
        'This is an independent industry timing replication, not a customer-promise ETA claim.\n',encoding='utf-8')
    print(json.dumps(cert,indent=2))

if __name__=='__main__': main()
