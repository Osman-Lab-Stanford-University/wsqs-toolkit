"""Local CORE-8 scoring of one household's response labels (no data saved)."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'src'))
from wsqs.response_coding import score_responses
from wsqs.scoring import CORE8

def main():
    parser=argparse.ArgumentParser(description='Score one CORE-8 survey JSON locally')
    parser.add_argument('--input', type=Path, default=HERE/'example/international_core8_example.json')
    args=parser.parse_args()
    data=json.loads(args.input.read_text(encoding='utf-8'))
    if not isinstance(data,dict): raise ValueError('Expected a JSON object of original question IDs to answer labels')
    allowed={qid for qid,_ in CORE8}
    if set(data)-allowed: raise ValueError('Unknown CORE-8 question ID')
    result=score_responses(data)
    n_scored=sum(1 for qid,_ in CORE8 if data.get(qid) not in (None,'','We have a full water system in-house (not dependent on any provider)'))
    print(json.dumps({'WSQS_100':result['CORE8'],'scored_domain_count':n_scored,'coverage_warning':n_scored<7,'interpretation':'Household-reported service experience; not a water-safety test.'},indent=2))
if __name__=='__main__': main()
