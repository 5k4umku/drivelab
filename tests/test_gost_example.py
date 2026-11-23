import json
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from engine import calculate


class PublishedExample(unittest.TestCase):
    def test_published_project_recomputes_annex11(self):
        file=Path(__file__).resolve().parents[1]/'examples'/'gost-annex-11.json'
        r=calculate(json.loads(file.read_text(encoding='utf-8'))['input'])
        self.assertEqual(r['errors'],[])
        rt=r['rating']
        self.assertTrue(rt['available'],rt.get('reason'))
        self.assertAlmostEqual(r['T'],1970)
        self.assertAlmostEqual(r['chosen']['Ft'],2000*1970/r['chosen']['d1'])
        trace={x['title']:x['value'] for x in rt['trace']}
        for key,printed,tol in [('ZH',2.41,.005),('wHv',31,.05),('wFv',46.6,.1),
                                ('ZN1',1.05,.005),('ZN2',1.1,.005),('YFS1',3.83,.01),
                                ('σFlimb1',1000,.01),('σFlimb2',580,.01)]:
            self.assertAlmostEqual(trace[key],printed,delta=tol,msg=key)
        self.assertEqual(trace['σHlim1'],23*58)
        self.assertAlmostEqual(rt['HP'],min(rt['hp']))
        self.assertAlmostEqual(rt['sigmaH'],764.41,delta=.02)
        for values,expected in [(rt['sigmaF'],(227.85,217.01)),(rt['fp'],(606.67,347.41))]:
            for actual,value in zip(values,expected):
                self.assertAlmostEqual(actual,value,delta=.02)
        self.assertTrue(rt['mandatoryPending'])
