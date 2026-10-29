"""Regression, physical invariants and boundary handling. No browser required."""
import copy
import json
import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from engine import calculate,DEFAULTS,material_pair,r10

class SeminarRegression(unittest.TestCase):
    def test_recovered_historical_equal_hardness_arithmetic(self):
        p={**DEFAULTS,'sigmaH2':690,'sigmaF2':550,'NHG2':29,'hb2min':293,'hb2max':331}
        r=calculate(p)
        # Independently recalculated decimal reference from the original seminar.
        self.assertAlmostEqual(r['T'],14.900709219858156,11)
        self.assertAlmostEqual(r['ap'],145.7470354808104,9)
        self.assertAlmostEqual(r['ac'],170.7013193326169,9)
        self.assertAlmostEqual(r['mmin'],.3812749599619567,10)
        self.assertEqual([(v['m'],v['z1'],v['z2']) for v in r['variants']],[(1.25,43,271),(1.5,36,227),(2.,26,163),(2.5,21,131)])
        self.assertAlmostEqual(r['chosen']['Fa'],106.86333969544657,9)
        self.assertTrue(any(c['title'].startswith('Твёрдость') and c['status']=='fail' for c in r['checks']))

    def test_new_material_rule_updates_allowables(self):
        p=material_pair(DEFAULTS)
        self.assertEqual((p['rowName1'],p['rowName2']),('У785','У685'))
        self.assertEqual((p['sigmaH1'],p['sigmaH2']),(690,640))
        self.assertEqual((p['sigmaF1'],p['sigmaF2']),(550,500))
        r=calculate(p)
        self.assertAlmostEqual(r['HP'],640*.9/1.3)
        self.assertGreater(r['ac'],170.7014)

    def test_material_lower_boundary(self):
        with self.assertRaises(ValueError): material_pair({**DEFAULTS,'row1':1})
        p=material_pair({**DEFAULTS,'row1':2})
        self.assertEqual(p['rowName2'],'У345')

class GeometryInvariants(unittest.TestCase):
    def test_three_types_and_variants_preserve_kinematics(self):
        for kind in ['spur','helical','herringbone']:
            r=calculate({**DEFAULTS,'gearType':kind})
            self.assertTrue(r['variants'],kind)
            for c in r['variants']:
                with self.subTest(kind=kind,m=c['m']):
                    self.assertAlmostEqual((c['d1']+c['d2'])/2,c['a'],9)
                    self.assertAlmostEqual(c['d2']/c['d1'],c['u'],12)
                    self.assertAlmostEqual(c['Ft']*c['d1']/2000,r['T'],11)
                    self.assertAlmostEqual(c['n2']*c['u'],DEFAULTS['speed'],10)
                    self.assertAlmostEqual(c['T2']*c['n2']/9550,DEFAULTS['power']*DEFAULTS['efficiency'],10)
                    self.assertEqual(math.gcd(c['z1'],c['z2']),1)
                    if kind in ['spur','herringbone']: self.assertEqual(c['Fa'],0)
                    if kind=='spur': self.assertEqual(c['beta'],0)
                    else: self.assertGreaterEqual(c['epsilonBeta'],1-1e-10)

    def test_single_module_not_removed(self):
        r=calculate({**DEFAULTS,'modules':'1.25'})
        self.assertEqual(len(r['variants']),1)

    def test_selection_recomputes_trace_and_rating(self):
        a=calculate(DEFAULTS); b=calculate({**DEFAULTS,'selectedModule':2})
        self.assertEqual(b['chosen']['m'],2)
        self.assertNotEqual(a['chosen']['Fa'],b['chosen']['Fa'])
        self.assertNotEqual(a['rating']['h'],b['rating']['h'])
        self.assertAlmostEqual(next(t['value'] for t in b['trace'] if t['title']=='Осевая сила'),b['chosen']['Fa'])

class InvalidInput(unittest.TestCase):
    def test_unknown_design_cases_are_not_silently_discarded(self):
        for key,value in [('x1',0.2),('reverse',True),('accuracy',13),('typo_power',5)]:
            with self.subTest(key=key):
                result=calculate({**DEFAULTS,key:value})
                self.assertTrue(result['errors'])
                self.assertEqual(result['variants'],[])

    def test_zero_negative_nan_infinite_and_wrong_types(self):
        for k,v in [('speed',0),('power',-1),('life',float('nan')),('ratio',float('inf')),('KA','oops'),('efficiency',2),('modules','0 1'),('gearType','internal')]:
            with self.subTest(key=k,value=v): self.assertTrue(calculate({**DEFAULTS,k:v})['errors'])

    def test_impossible_selection_has_no_fake_result(self):
        r=calculate({**DEFAULTS,'modules':'40'})
        self.assertIsNone(r['chosen'])
        self.assertEqual(r['status'],'fail')

    def test_r10_rounds_up_without_skipping_exact_value(self):
        self.assertEqual(r10(200),200)
        self.assertEqual(r10(200.01),250)
        self.assertEqual(r10(182.3),200)

    def test_results_are_json_finite(self):
        for k in ['spur','helical','herringbone']:
            json.dumps(calculate({**DEFAULTS,'gearType':k},compare=True),allow_nan=False)

if __name__=='__main__': unittest.main()
