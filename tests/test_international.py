import csv
import json
import unittest
from pathlib import Path
import pandas as pd
from wsqs.scoring import core8
from wsqs.response_coding import score_responses
from wsqs.extended import DOMAINS, domain_severities, household_priorities

ROOT=Path(__file__).resolve().parents[1]

class InternationalInstrumentTests(unittest.TestCase):
    def test_questionnaire_has_43_traceable_questions(self):
        with (ROOT/'survey/WSQS_International_Question_Codebook.csv').open(encoding='utf-8',newline='') as f:
            rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),43)
        self.assertEqual(len(set(r['Question_ID'] for r in rows)),43)
        self.assertEqual(sum(r['Role']=='CORE8 outcome' for r in rows),8)
        self.assertEqual(sum(r['Role']=='Service-support predictor' for r in rows),22)
        self.assertEqual(sum(r['Role']=='Household context predictor' for r in rows),3)
        self.assertEqual(sum(r['Role']=='Priority predictor' for r in rows),8)
        self.assertEqual(sum(r['Role']=='Provision eligibility support' for r in rows),2)
    def test_original_core8_response_mapping(self):
        response=json.loads((ROOT/'example/international_core8_example.json').read_text())
        self.assertAlmostEqual(score_responses(response)['CORE8'],78.57142857142857)
        response['Q9.1']='Excellent'
        self.assertAlmostEqual(score_responses(response)['CORE8'],81.25)
    def test_invalid_fractional_core8_severity_rejected(self):
        with self.assertRaises(ValueError): core8({'Q2.2':2.5})
        frame=pd.DataFrame({f'{domain}_raw_severity':[3.0] for domain in DOMAINS})
        frame.loc[0,'Quality_raw_severity']=2.5
        with self.assertRaises(ValueError): domain_severities(frame)
    def test_noninteger_priorities_rejected(self):
        frame=pd.DataFrame({f'{domain}_priority_0_10':[7.0] for domain in DOMAINS})
        frame.loc[0,'Quality_priority_0_10']=7.5
        with self.assertRaises(ValueError): household_priorities(frame)
    def test_customer_service_inapplicability_is_not_bad_service(self):
        response=json.loads((ROOT/'example/international_core8_example.json').read_text())
        scored=score_responses(response)['CORE8']
        self.assertAlmostEqual(scored,78.57142857142857)
        self.assertTrue(0<=scored<=100)
