import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from gost_duty import equivalent_cycles, equivalent_stress


def level(torque, cycles, speed=1000, zv=1):
    return dict(torque=torque, speed=speed, cycles=cycles, zv=zv)


class EquivalentStressTests(unittest.TestCase):
    def test_mixed_knee_weighted_over_accepted_cycles(self):
        rows = [dict(stress=s, cycles=n) for s, n in ((1200, 1e6), (950, 2e6), (749, 3e6), (1000, 30000))]
        r = equivalent_stress(rows, kind='contact', limit_mpa=1000, base_cycles=1e6)
        expected = ((1200**6+2*950**20/1000**14)/3)**(1/6)
        self.assertAlmostEqual(r['stress'], expected)
        self.assertEqual(r['included'], [0, 1])
        self.assertEqual(r['cycles'], 3e6)
        self.assertEqual(r['branch'], 'mixed')

    def test_lower_upper_and_threshold_equality(self):
        for stresses, power, branch in [((750, 990), 20, 'lower'), ((1000, 1200), 6, 'upper')]:
            rows = [dict(stress=s, cycles=100000) for s in stresses]
            r = equivalent_stress(rows, kind='contact', limit_mpa=1000, base_cycles=1e6)
            self.assertAlmostEqual(r['stress'], (sum(s**power for s in stresses)/2)**(1/power))
            self.assertEqual(r['branch'], branch)
        r = equivalent_stress([dict(stress=900, cycles=30000)], kind='contact', limit_mpa=1000, base_cycles=1e6)
        self.assertIsNone(r['stress'])
        self.assertEqual(r['cycles'], 0)

    def test_splitting_a_stress_level_and_bending_without_contact_cutoff(self):
        r = equivalent_stress([dict(stress=1100, cycles=16000)]*2,
                              kind='contact', base_cycles=1e6, limit_mpa=1000)
        self.assertEqual(r['stress'], 1100)
        self.assertEqual(r['included'], [0, 1])
        r = equivalent_stress([dict(stress=300, cycles=1), dict(stress=600, cycles=2)],
                              kind='bending', limit_mpa=500, q=9)
        self.assertAlmostEqual(r['stress'], ((300**9+2*600**9)/3)**(1/9))


class EquivalentCycleTests(unittest.TestCase):
    def test_formula_45_and_brief_overload(self):
        rows = [level(125, 1000), level(100, 5e5), level(50, 2.5e5)]
        r = equivalent_cycles(rows, kind='contact', base_cycles=1e6, dynamic=0)
        self.assertEqual(r['torque'], 100)
        self.assertEqual(r['referenceIndex'], 1)
        self.assertEqual(r['overloads'], [0])
        self.assertAlmostEqual(r['cycles'], 1000*1.25**3+5e5+2.5e5*.5**3)

    def test_variable_speed_and_dynamic(self):
        rows = [level(100, 30000, 500, .9), level(75, 50000, 1000, 1.1)]
        r = equivalent_cycles(rows, kind='contact', base_cycles=1e6, dynamic=.2)
        self.assertAlmostEqual(r['cycles'], 30000+50000*((.75+.2*2)/1.2)**3*(.9/1.1)**6)
        self.assertEqual(r['referenceIndex'], 0)

    def test_two_stopping_conditions(self):
        r = equivalent_cycles([level(100, 1e6), level(50, 1e6)], kind='contact', base_cycles=1e6, dynamic=0)
        self.assertEqual(r['branch'], 'cutoff')
        self.assertEqual(r['cycles'], 1e6)
        r = equivalent_cycles([level(100, 8e6)], kind='contact', base_cycles=1e6, dynamic=0)
        self.assertEqual(r['branch'], 'partial')
        self.assertAlmostEqual(r['factor'], (1/.75)**3)

    def test_bending_reference_threshold_and_external_reference(self):
        rows = [level(110, 50000), level(100, 50001), level(50, 90000)]
        opts = dict(kind='bending', base_cycles=4e6, dynamic=.1, q=6, contact_reference=dict(torque=100, speed=1000))
        r = equivalent_cycles(rows, **opts)
        self.assertEqual(r['referenceIndex'], 1)
        self.assertEqual(r['overloads'], [0])
        expected = 50000*(120/110)**6 + 50001 + 90000*(60/110)**6
        self.assertAlmostEqual(r['cycles'], expected)
        r = equivalent_cycles(rows, reference_index=0, **opts)
        self.assertTrue(r['notes'])
        self.assertEqual(r['overloads'], [])

    def test_input_domains(self):
        for row in (dict(stress=750, cycles=True), dict(stress=-1, cycles=1), dict(stress=1000, cycles=0)):
            with self.subTest(row=row), self.assertRaises(ValueError):
                equivalent_stress([row], kind='contact', limit_mpa=1000, base_cycles=1e6)
        with self.assertRaises(ValueError):
            equivalent_cycles([level(100, 29999)], kind='contact', base_cycles=1e6, dynamic=0)
