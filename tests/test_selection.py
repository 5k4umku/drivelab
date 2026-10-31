import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from selection import zubil,tooth_pairs
from tolerances import fit,tolerance
from engine import DEFAULTS,calculate
from assembly import from_single, new_shaft
from automation import search,inspect

class SelectionTests(unittest.TestCase):
    def test_both_neighbours_not_only_round(self):
        pairs=tooth_pairs(10,10,2)
        self.assertEqual([(p['z1'],p['z2']) for p in pairs],[(3,7),(4,6)])

    def test_max_lcm_inside_tolerance(self):
        r=zubil(80,90,3,3)
        self.assertEqual((r['best']['z1'],r['best']['z2']),(23,67))
        self.assertEqual(r['best']['lcm'],1541)
        self.assertEqual(r['best']['turns'],67)
        self.assertTrue(r['withinTolerance'])

    def test_fallback_is_not_reported_as_accepted(self):
        r=zubil(10,10,2,1)
        self.assertFalse(r['withinTolerance'])
        self.assertEqual(r['best']['z1'],3)

    def test_exact_and_reversed_bounds(self):
        self.assertEqual(zubil(90,80,3),zubil(80,90,3))
        self.assertEqual(len(tooth_pairs(80,80,3)),1)

    def test_invalid_and_unsafe_domains(self):
        for args in [(0,20,3),(10,10.1,.3),(2,20000,3),(True,20,3),(10.2,10.4,3)]:
            with self.assertRaises(ValueError): tooth_pairs(*args)

    def test_table_interval_boundary(self):
        self.assertEqual(tolerance(30,7),21)
        self.assertEqual(tolerance(30.000001,7),25)
        self.assertEqual(tolerance(50,6),16)
        self.assertEqual(tolerance(50.1,6),19)
        with self.assertRaises(ValueError): tolerance(501,7)

    def test_h7_h6_arithmetic(self):
        r=fit(40,7,6)
        self.assertEqual(r['holeMax'],40.025)
        self.assertEqual(r['shaftMin'],39.984)
        self.assertEqual(r['gapMax'],.041)

    def test_sensitive_fixed_geometry(self):
        r=calculate(DEFAULTS);before=copy.deepcopy(r)
        a=inspect(r,10)
        self.assertEqual(r,before)
        self.assertLess(a['scenarios'][0]['h'],a['scenarios'][2]['h'])
        self.assertLess(a['scenarios'][0]['f'],a['scenarios'][2]['f'])
        self.assertIsNone(a['grades'][-1]['margin'])

    def test_search_checks_complete_project_and_preserves_it(self):
        p=from_single();before=copy.deepcopy(p)
        r=search(p)
        self.assertEqual(p,before)
        self.assertEqual(r['count'],24)
        self.assertGreater(r['accepted'],0)
        self.assertTrue(all(x['margin']>=1 for x in r['rows'] if x['eligible']))
        self.assertGreater(r['rows'][0]['pending'],0)

    def test_zubil_engine_has_full_strength_result(self):
        r=calculate({**DEFAULTS,'selectionPolicy':'zubil'})
        self.assertEqual((r['chosen']['z1'],r['chosen']['z2']),(43,273))
        self.assertTrue(r['rating']['available'])
        self.assertFalse(r['rating']['complete'])

    def test_search_rejects_unrated_other_stage(self):
        p=from_single({'ratio':3})
        p['stages'].append(dict(input={**DEFAULTS,'meshType':'internal','ratio':3,'faceMode':'manual'},angle=60,axial=None,hand='right'))
        p['shafts']=[new_shaft() for _ in range(3)]
        r=search(p)
        self.assertEqual(r['accepted'],0)
        self.assertTrue(any('Ступень 2: прочность вне' in row.get('reason','') for row in r['rows']))

    def test_search_rejects_failed_other_stage(self):
        p=from_single({'ratio':3})
        p['stages'].append(dict(input={**DEFAULTS,'ratio':3,'aOverride':100,'psiBd':.6,'faceMode':'manual','modules':'1 1.25 1.5 2'},angle=60,axial=None,hand='right'))
        p['shafts']=[new_shaft() for _ in range(3)]
        r=search(p)
        self.assertEqual(r['accepted'],0)
        self.assertTrue(any('Ступень 2:' in row.get('reason','') for row in r['rows']))

if __name__=='__main__': unittest.main()
