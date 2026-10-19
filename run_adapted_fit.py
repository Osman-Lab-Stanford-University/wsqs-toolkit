"""Fit a new CatBoost forecast to an independently prepared, harmonized dataset.

Research adaptation, not reproduction of historical India model results.
Input data is read locally; no respondent-level output is written.
"""
from __future__ import annotations
import argparse, hashlib, json, os, platform, shutil, sys
from datetime import datetime, timezone
from pathlib import Path
from importlib import metadata
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'src'))
from wsqs.features import feature_specification
from wsqs.models import catboost_predictions, model_settings, prepare_catboost, summary_metrics

def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()

def main():
    a=argparse.ArgumentParser(description='Adapt WSQS forecasting to your own harmonized data')
    a.add_argument('--input',type=Path,required=True,help='CSV with 33 harmonized model features and WSQS_100 target')
    a.add_argument('--output',type=Path,required=True,help='A new, NONEXISTENT private output directory')
    a.add_argument('--seed',type=int,default=20260714)
    args=a.parse_args()
    path=args.input.resolve();output=args.output.resolve()
    if not path.is_file():raise FileNotFoundError(path)
    if output.exists():raise FileExistsError('Output exists; historical artifacts cannot be overwritten')
    if output==HERE or HERE in output.parents:raise ValueError('Store private results outside the public source directory')
    data=pd.read_csv(path,low_memory=False)
    spec=feature_specification()
    cols=list(spec['columns']['all']) if 'columns' in spec else None
    if cols is None:
        feature_meta=__import__('csv').DictReader((HERE/'questionbook/feature_manifest.csv').open(newline='',encoding='utf-8'))
        cols=[r['feature'] for r in feature_meta]
    if len(cols)!=33 or len(set(cols))!=33:raise ValueError('Expected 33 original predictor columns')
    missing=[c for c in cols+['WSQS_100'] if c not in data.columns]
    if missing:raise ValueError('Missing harmonized columns: '+', '.join(missing))
    if len(data)<100:raise ValueError('At least 100 independently collected records required for example fitting')
    y=pd.to_numeric(data['WSQS_100'],errors='coerce')
    if y.isna().any() or not np.isfinite(y).all() or not y.between(0,100).all():raise ValueError('Invalid WSQS_100 target')
    numeric=[r['feature'] for r in __import__('csv').DictReader((HERE/'questionbook/feature_manifest.csv').open(encoding='utf-8')) if r['type']=='numeric']
    categorical=[c for c in cols if c not in numeric]
    X=data[cols].copy()
    for col in numeric:
        old=X[col];new=pd.to_numeric(old,errors='coerce')
        if (old.notna() & new.isna()).any():raise ValueError('Unrecognized numeric predictor values: '+col)
        X[col]=new
    X=prepare_catboost(X,categorical,numeric)
    n=len(X)
    dev,test=train_test_split(np.arange(n),test_size=.2,random_state=args.seed)
    fit,val=train_test_split(dev,test_size=.2,random_state=args.seed)
    config=model_settings();config['catboost']['random_seed']=args.seed
    predicted,iterations=catboost_predictions(X,y,categorical,fit,val,test,np.sort(dev),config)
    score=summary_metrics(y.iloc[test],predicted)
    status={'status':'ADAPTED_NEW_POPULATION_NOT_ORIGINAL_STUDY','record_count':n,'feature_count':33,'seed':args.seed,'fit_n':len(fit),'validation_n':len(val),'test_n':len(test),'selected_iterations':iterations,'metrics':score,'model_scope':'new local study only','individual_predictions_written':False,'input_sha256':sha256(path),'utc':datetime.now(timezone.utc).isoformat()}
    # Preserve the exact relevant source/config copied with output. No individual records.
    output.mkdir(parents=True,exist_ok=False)
    source_dir=output/'executed_sources';source_dir.mkdir()
    for rel in ['run_adapted_fit.py','src/wsqs/models.py','src/wsqs/features.py','src/wsqs/scoring.py','config/models.json','config/feature_spec.json','questionbook/feature_manifest.csv']:
        dest=source_dir/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(HERE/rel,dest)
    status['source_hashes']={p.relative_to(source_dir).as_posix():sha256(p) for p in source_dir.rglob('*') if p.is_file()}
    status['environment']={'python':platform.python_version(),**{k:metadata.version(k) for k in ['catboost','scikit-learn','numpy','pandas']}}
    (output/'aggregate_results.json').write_text(json.dumps(status,indent=2)+'\n',encoding='utf-8')
    (output/'execution_log.txt').write_text('RUN: run_adapted_fit.py\n'+json.dumps(status,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(status,indent=2))
if __name__=='__main__': main()
