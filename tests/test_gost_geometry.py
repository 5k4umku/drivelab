"""Таблица 38 и независимые геометрические соотношения для смещённой пары."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from gost_geometry import external_geometry, pair_stiffness, tooth_form_factor


class GeometryTests(unittest.TestCase):
    def test_appendix_11_table_38(self):
        geom = external_geometry(5, 32, 64, 16 + 15 / 60, 60, 1500)
        # В таблице до подстановки округлены cos β до 0,96 и cos αt до 0,935.
        for key, value, tolerance in (
            ('alphaT', 20.76, .005), ('alphaTW', 20.76, .005), ('aW', 250., .02),
            ('d1', 166.667, .01), ('d2', 333.334, .02), ('da1', 176.667, .01),
            ('da2', 343.334, .02), ('db1', 155.834, .002), ('db2', 311.666, .005),
            ('alphaA2', 24.80, .01), ('epsilonA1', .790, .002),
            ('epsilonA2', .846, .003), ('epsilonAlpha', 1.64, .01),
            ('pX', 56.13, .01), ('epsilonBeta', 1.07, .002), ('epsilonGamma', 2.71, .01),
            ('betaB', 15.25, .01), ('zv1', 36.2, .05), ('zv2', 72.4, .08),
            ('v', 13.1, .02),
        ):
            with self.subTest(key=key):
                self.assertAlmostEqual(geom[key], value, delta=tolerance)
        # В п. 7 ошибочно напечатано 29,11°. Следующая строка использует tan≈0,534.
        self.assertAlmostEqual(geom['alphaA1'], 28.10, places=2)

    def test_shifted_pair_matches_path_length_and_pitch_diameters(self):
        g = external_geometry(2, 24, 48, 0, 20, 1000, .4, .2)
        self.assertGreater(g['aW'], g['a'])
        self.assertGreater(g['alphaTW'], g['alphaT'])
        self.assertIsNone(g['pX'])
        self.assertEqual(g['epsilonBeta'], 0)
        atw = math.radians(g['alphaTW'])
        at = math.radians(g['alphaT'])
        self.assertAlmostEqual(math.tan(atw) - atw, math.tan(at) - at + 1.2 * math.tan(at) / 72)
        self.assertAlmostEqual(g['dw1'] + g['dw2'], 2 * g['aW'])
        path = sum(math.sqrt(g[f'da{i}']**2 - g[f'db{i}']**2)/2 for i in (1, 2))
        path -= g['aW'] * math.sin(atw)
        self.assertAlmostEqual(g['epsilonAlpha'], path / (math.pi * 2 * math.cos(at)))

    def test_compensated_shifts_and_left_hand_helix(self):
        original = external_geometry(3, 30, 60, 20, 25, 1500)
        changed = external_geometry(3, 30, 60, -20, 25, 1500, .25, -.25)
        for key in ('aW', 'd1', 'd2', 'alphaTW', 'epsilonBeta'):
            self.assertEqual(changed[key], original[key])
        self.assertEqual(changed['betaB'], -original['betaB'])
        self.assertAlmostEqual(changed['da1'] - original['da1'], 1.5)
        self.assertNotEqual(changed['epsilonAlpha'], original['epsilonAlpha'])

    def test_invalid_inputs_and_impossible_geometry(self):
        for args in ((0, 24, 48, 0, 25, 1000), (2, 24, True, 0, 25, 1000),
                     (2, 24, 48.1, 0, 25, 1000), (2, 24, 48, 90, 25, 1000),
                     (2, 24, 48, 0, 25, 1000, -.8, -1), (2, 3, 60, 0, 25, 1000),
                     (2, 24, 48, 0, 25, 1000, float('nan'), 0)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                external_geometry(*args)

    def test_shifted_factors_both_tools(self):
        self.assertAlmostEqual(pair_stiffness(25, 50, .3, -.15), 18.045671791)
        self.assertAlmostEqual(tooth_form_factor(25, .3), 3.64988)
        self.assertAlmostEqual(tooth_form_factor(50, -.15, 'protuberance'), 4.240725)
        with self.assertRaises(ValueError):
            tooth_form_factor(50, 0, 'other')


if __name__ == '__main__':
    unittest.main()
