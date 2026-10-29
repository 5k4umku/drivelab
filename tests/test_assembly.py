import copy
import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from assembly import beam_reactions, calculate_assembly, from_single, new_shaft
from engine import calculate, DEFAULTS


def two_stage():
    p = from_single()
    p['stages'].append(dict(input={**DEFAULTS, 'ratio': 3, 'modules': '1 1.25 1.5 2 2.5 3 4 5 6 8 10'}, angle=0, axial=None, hand='left'))
    p['shafts'] = [new_shaft() for _ in range(3)]
    return p


class BeamTests(unittest.TestCase):
    def test_center_load_independent_reference(self):
        r = beam_reactions([dict(position=[0, 0, 50], force=[0, -500, 0])], 0, 100)
        self.assertEqual(r['A']['vector'], [0, 250, 0])
        self.assertEqual(r['B']['vector'], [0, 250, 0])
        self.assertEqual(r['maxBending'], 12.5)

    def test_overhung_load_reverses_far_reaction(self):
        r = beam_reactions([dict(position=[0, 0, -50], force=[0, -100, 0])], 0, 100)
        self.assertEqual(r['A']['vector'][1], 150)
        self.assertEqual(r['B']['vector'][1], -50)
        self.assertEqual(r['maxBending'], 5)

    def test_axial_force_at_pitch_radius_creates_bending(self):
        r = beam_reactions([dict(position=[20, 0, 50], force=[0, 0, 100])], 0, 100, 'B')
        self.assertEqual(r['A']['vector'], [-20, 0, 0])
        self.assertEqual(r['B']['vector'], [20, 0, -100])
        self.assertEqual(r['maxBending'], 1)

    def test_superposition_and_translation(self):
        loads = [dict(position=[20, 0, 20], force=[130, 70, 40]), dict(position=[-30, 0, 80], force=[-30, -170, -60])]
        a = beam_reactions(loads, -20, 120)
        b = beam_reactions([{**l, 'position': [*l['position'][:2], l['position'][2]+500]} for l in loads], 480, 620)
        for key in ('A', 'B'):
            for x, y in zip(a[key]['vector'], b[key]['vector']): self.assertAlmostEqual(x, y)
        self.assertAlmostEqual(a['maxBending'], b['maxBending'])
        self.assertLess(max(map(abs, a['forceResidual']+a['momentResidual'])), 1e-10)


class AssemblyTests(unittest.TestCase):
    def test_global_ratio_error_uses_product_of_actual_teeth(self):
        p = two_stage(); p['ratioTolerance'] = 0
        a = calculate_assembly(p)
        self.assertAlmostEqual(a['targetRatio'], 6.3*3)
        self.assertAlmostEqual(a['ratioError'], abs(a['totalRatio']/(6.3*3)-1)*100)
        check = next(c for c in a['checks'] if c['title'] == 'Общее передаточное число')
        self.assertEqual(check['status'], 'fail')

    def test_manual_support_can_be_anywhere_but_reports_overlap(self):
        p = from_single()
        p['shafts'][0].update(layout='manual', zA=-10, zB=10)
        a = calculate_assembly(p)
        self.assertFalse(a['errors'])
        self.assertEqual(a['shafts'][0]['A']['z'], -10)
        self.assertTrue(any(c['status']=='fail' and 'опоры вне венца' in c['title'] for c in a['checks']))

    def test_legacy_geometry_is_preserved(self):
        a = calculate_assembly(from_single())
        b = calculate(DEFAULTS)
        self.assertFalse(a['errors'])
        self.assertEqual(a['stages'][0]['result']['chosen'], b['chosen'])

    def test_chain_uses_actual_ratio_and_efficiency(self):
        p = two_stage()
        p['stages'][0]['input']['efficiency'] = .9
        p['stages'][1]['input']['efficiency'] = .8
        a = calculate_assembly(p)
        self.assertFalse(a['errors'])
        self.assertAlmostEqual(a['outputPower'], 2.2*.9*.8)
        self.assertAlmostEqual(a['efficiency'], .72)
        self.assertAlmostEqual(a['outputSpeed'], 1410 / math.prod(s['result']['chosen']['u'] for s in a['stages']))
        self.assertEqual(a['stages'][1]['inputSpeed'], a['stages'][0]['outputSpeed'])
        self.assertEqual([s['signedSpeed'] > 0 for s in a['shafts']], [True, False, True])
        self.assertAlmostEqual(a['outputTorque'], 9550*a['outputPower']/a['outputSpeed'])
        for s in a['shafts']: self.assertLess(max(map(abs, s['forceResidual']+s['momentResidual'])), 1e-6)

    def test_support_movement_changes_reactions_not_power(self):
        p = from_single()
        a = calculate_assembly(p)
        p['shafts'][0]['layout'] = 'centered'
        b = calculate_assembly(p)
        self.assertNotEqual(a['shafts'][0]['A']['radial'], b['shafts'][0]['A']['radial'])
        self.assertEqual(a['outputPower'], b['outputPower'])

    def test_overlapping_stages_are_reported(self):
        p = two_stage()
        p['stages'][1]['axial'] = 0
        a = calculate_assembly(p)
        self.assertTrue(a['collisions'])
        p['stages'][1]['axial'] = None
        b = calculate_assembly(p)
        self.assertFalse(any('венцы ступеней' in s for s in b['collisions']))

    def test_layout_rotation_preserves_reaction_norms(self):
        p = from_single()
        a = calculate_assembly(p)
        p['stages'][0]['angle'] = 90
        b = calculate_assembly(p)
        for x, y in zip(a['shafts'], b['shafts']):
            self.assertAlmostEqual(x['A']['radial'], y['A']['radial'])
            self.assertAlmostEqual(x['maxBending'], y['maxBending'])

    def test_hand_changes_axial_direction(self):
        p = from_single()
        a = calculate_assembly(p)
        p['stages'][0]['hand'] = 'left'
        b = calculate_assembly(p)
        self.assertAlmostEqual(a['gears'][0]['force'][2], -b['gears'][0]['force'][2])
        self.assertEqual(a['outputSpeed'], b['outputSpeed'])

    def test_invalid_project_is_rejected(self):
        for mutate in [lambda p: p['shafts'].pop(), lambda p: p.update(power=float('nan')),
                       lambda p: p['shafts'][0].update(layout='manual', zA=10, zB=10),
                       lambda p: p['stages'][0].update(angle=True), lambda p: p.update(branch=True)]:
            p = from_single(); mutate(p)
            self.assertTrue(calculate_assembly(p)['errors'])

    def test_stage_errors_do_not_reuse_previous_result(self):
        p = two_stage(); p['stages'][1]['input']['ratio'] = 0
        a = calculate_assembly(p)
        self.assertTrue(a['errors'])
        self.assertEqual(a['shafts'], [])


if __name__ == '__main__': unittest.main()
