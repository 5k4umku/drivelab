import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from gost_subsurface import boundary_from_chart, deep_contact, nitriding_graphs, profile_hardness, reduced_radius


def fixture(**edits):
    p = dict(treatment='carburized', surface_hv=750, core_hv=400, thickness=2,
             rho=15, line_load=300, elastic_modulus=210000, peak_ratio=2,
             sigma_h=1200, sigma_max=1700, profile_confirmed=True, confirmed_depth=.22,
             steel_group='low_alloy', controlled=True)
    p.update(edits)
    return deep_contact(**p)


class SubsurfaceTests(unittest.TestCase):
    def test_figure_30_example(self):
        # В подписи к чертежу для 400 HV, 2 мм и 15 мм указано 2960 МПа.
        graph = boundary_from_chart(400, 2, 15)
        self.assertEqual(graph['D'], 168)
        self.assertAlmostEqual(graph['K']/1e6, 11.38, places=2)
        self.assertLess(abs(graph['value']-2960), 10)
        self.assertEqual((graph['lower'], graph['upper']), (2750, 3000))
        with self.assertRaises(ValueError):
            boundary_from_chart(500, 2, 15)

    def test_zones_layers_and_core(self):
        r = fixture()
        self.assertTrue(r['complete'])
        self.assertEqual(r['fatigue']['zone'], 'layer')
        self.assertEqual(r['peak']['zone'], 'boundary')
        self.assertAlmostEqual(r['fatigue']['allowable'], 3.6*750 / (1+.875*(.42/2)**2) / 1.4)
        r = fixture(confirmed_depth=2.1, sigma_h=1300)
        self.assertEqual(r['fatigue']['limits'], {'core': 1440})
        self.assertEqual(r['peak']['limits'], {'core': 2880})
        self.assertFalse(r['fatigue']['passed'])
        self.assertTrue(r['complete'])
        r = fixture(confirmed_depth=1.9, peak_ratio=2, surface_hv=1200)
        self.assertEqual(r['peak']['zone'], 'core')
        self.assertIn('boundary', r['fatigue']['limits'])

    def test_hardness_profiles(self):
        for treatment in ('carburized', 'nitrided', 'carbonitrided'):
            self.assertEqual(profile_hardness(treatment, 800, 400, 0), 800)
            self.assertEqual(profile_hardness(treatment, 800, 400, 1), 400)
        self.assertEqual(profile_hardness('nitrided', 800, 400, .5), 520)
        self.assertEqual(profile_hardness('carburized', 800, 400, .5), 640)

    def test_nitriding_and_lower_life_bound(self):
        self.assertEqual(nitriding_graphs(3, 2.2), (8.16, .933))
        r = fixture(treatment='nitrided', surface_hv=880, thickness=1.8, cycles=1e8)
        self.assertEqual(r['parameters']['ZLK'], 1)
        self.assertAlmostEqual(r['fatigue']['allowable'], 1.07*8.16*.933*400/1.4)
        r = fixture(treatment='nitrided', surface_hv=880, thickness=1.8, cycles=1e6, confirmed_depth=None)
        self.assertGreater(r['parameters']['ZLK'], 1)
        self.assertTrue(r['fatigue']['passed'])
        self.assertIsNone(r['peak'])
        self.assertTrue(r['complete'])
        self.assertEqual(r['warnings'], [])

    def test_reading_graphs_near_limit_or_outside_range(self):
        r = fixture(sigma_max=2630)
        self.assertIsNone(r['peak']['passed'])
        r = fixture(sigma_max=2630, boundary_mpa=2960)
        self.assertTrue(r['peak']['passed'])
        r = fixture(thickness=5)
        self.assertIsNotNone(r['fatigue']['passed'])
        self.assertIsNone(r['peak']['passed'])
        r = fixture(treatment='nitrided', surface_hv=850, thickness=.3, cycles=1e7, confirmed_depth=.4)
        self.assertIsNone(r['fatigue']['passed'])
        self.assertIsNone(r['peak'])

    def test_required_evidence(self):
        r = fixture(confirmed_depth=None)
        self.assertFalse(r['complete'])
        self.assertIsNone(r['fatigue']['passed'])
        self.assertIsNone(r['peak']['passed'])
        self.assertAlmostEqual(r['parameters']['hH'], 1.52*math.sqrt(300*15/210000))
        self.assertAlmostEqual(r['parameters']['printedDepth'], 1.52*15*math.sqrt(300/210000))
        self.assertIsNone(fixture(profile_confirmed=False)['fatigue']['passed'])
        with self.assertRaisesRegex(ValueError, 'SHK'):
            fixture(steel_group='carbon', controlled=False)
        self.assertTrue(fixture(steel_group='carbon', controlled=False, safety=1.6)['complete'])
        self.assertAlmostEqual(reduced_radius(120, 3, 30), 20.4)
        for args in ({'profile_confirmed': 'да'}, {'treatment': 'У'}, {'thickness': 0},
                     {'confirmed_depth': float('nan')}, {'peak_ratio': .98}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                fixture(**args)
