import json
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from engine import calculate


class RootFatigueTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'examples/gost-root-fatigue.json').read_text(encoding='utf8'))['input']
        self.cfg = self.data['gost']

    def run_rating(self):
        return calculate(self.data)['rating']

    def test_control_pair_only_changes_fatigue_allowables(self):
        self.cfg['design'] = {}
        updated = calculate(self.data)
        del self.cfg['roots']
        reference = calculate(self.data)
        r, ref = updated['rating'], reference['rating']
        self.assertTrue(r['available'], r.get('reason'))
        for i, (radius, yd) in enumerate([(8.976, .938966447), (9.781546667, .912194723)]):
            self.assertAlmostEqual(r['roots'][i]['radius'], radius, places=8)
            self.assertAlmostEqual(r['roots'][i]['Ydelta'], yd, places=8)
            self.assertAlmostEqual(r['fp'][i]/ref['fp'][i], yd/.874891363, places=7)
        for key in ('YFS','fs','fpmax','fsmax','hp','h'):
            self.assertEqual(r[key], ref[key], key)
        self.assertTrue(updated['design']['available'], updated['design'].get('reason'))
        self.assertEqual(updated['design'], reference['design'])

    def test_measured_radius_at_threshold_and_one_member_only(self):
        for radius, expected in [(6.9999,(.874891363,.874891363)), (7,(.874891363,.874891363)),
                                 (7.0001,(.942374152,.926780523))]:
            for i in range(2):
                with self.subTest(radius=radius, member=i):
                    roots = [None, None]
                    roots[i] = dict(radiusMm=radius, uncertaintyMm=.00001 if radius!=7 else 0,
                                    section='Нормальное сечение, точка A', evidence='Протокол контроля')
                    self.cfg['roots'] = roots
                    rt = self.run_rating()
                    self.assertTrue(rt['available'], rt.get('reason'))
                    self.assertIsNone(rt['roots'][1-i])
                    self.assertAlmostEqual(rt['roots'][i]['Ydelta'], expected[i], places=8)
                    step = next(x for x in rt['trace'] if x['title']==f'Yδ{i+1}')
                    self.assertIn('Протокол контроля', step['substitution'])

    def test_limits_never_silently_select_a_formula(self):
        measured = dict(radiusMm=8, uncertaintyMm=.05, section='Нормальное сечение, точка A', evidence='Протокол')
        for patch in [dict(evidence=''), dict(section=''), dict(uncertaintyMm=None),
                      dict(radiusMm=7.01), dict(grindingStep=True), dict(tipTest={})]:
            self.cfg['roots'] = [dict(measured, **patch), None]
            self.assertFalse(self.run_rating()['available'], patch)
        self.cfg['roots'] = [dict(evidence='Чертёж',curveConfirmed=True), None]
        self.data['x1'] = .1
        self.assertIn('12а', self.run_rating()['reason'])
        self.data['x1'] = 0
        self.cfg['roots'] = [None, dict(evidence='Чертёж',curveConfirmed=True)]
        self.assertIn('12б', self.run_rating()['reason'])
        self.cfg['roots'] = [measured, None]
        del self.cfg['materials'][0]['yieldStrength']
        self.assertFalse(self.run_rating()['available'])

    def test_table17_coverage_and_unconfirmed_groups(self):
        from gost_root import root_parameters
        cfg = dict(radiusMm=8, uncertaintyMm=.02, section='Сечение A', evidence='Измерение')
        def evaluate(row, strength=None, **patch):
            return root_parameters(dict(cfg, **patch), module=16, zv=30, x=0, tool='standard',
                                   material_row=row, yield_strength=strength, spur=True)
        for row, strength, patch in [
            ('17.7',700,{}), ('17.7',None,dict(baseHardened=False)),
            ('17.4',None,dict(baseHardened=False)), ('16.5',None,{}), ('16.2',700,{}),
            ('Т1',700,dict(materialEvidence='Карта обработки')),
        ]:
            with self.subTest(row=row, strength=strength, patch=patch), self.assertRaises(ValueError):
                evaluate(row, strength, **patch)
        self.assertEqual(evaluate('17.7',700,baseHardened=False)['gradientBranch'], 'unhardenedRoot')
        self.assertEqual(evaluate('17.4',baseHardened=True)['gradientBranch'], 'hardenedRoot')
        self.assertAlmostEqual(evaluate('Т1',yieldStrength=700,materialEvidence='Паспорт улучшения')['Ydelta'],
                               evaluate('16.1',700)['Ydelta'])
