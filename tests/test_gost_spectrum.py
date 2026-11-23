import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from engine import calculate
from gost_spectrum import moments


def level(t, f):
    return dict(torqueRatio=t, timeFraction=f)


class SpectrumTests(unittest.TestCase):
    def test_weighted_moments_and_wheel_cycles(self):
        side, = moments([level(.5,.75),level(1,.25)],100,10,1200,4,[6,9])
        self.assertAlmostEqual(side['TH'],100*(.25+.75/8)**(1/3))
        self.assertAlmostEqual(side['TF'][1],100*(.25+.75/512)**(1/9))
        self.assertEqual(side['cycles'], [720000,180000])

    def test_constant_spectrum_matches_constant_load(self):
        base = calculate(dict(loadRegime='0',loadDirection='oneway'))['rating']
        actual = calculate(dict(gost=dict(spectrum=[level(1,1)])))['rating']
        self.assertTrue(actual['available'],actual.get('reason'))
        for key in base['margins']:
            self.assertAlmostEqual(actual['margins'][key], base['margins'][key])

    def test_two_flanks_use_actual_service_hours_and_peak(self):
        rt = calculate(dict(gost=dict(spectrum=[level(1,.5),level(-.5,.5)])))['rating']
        self.assertTrue(rt['available'],rt.get('reason'))
        spectrum=rt['spectrum']
        self.assertEqual([s['hours'] for s in spectrum['flanks']],[5000,5000])
        for ya in spectrum['YA']:
            self.assertAlmostEqual(ya,1-.35*.5)
        self.assertAlmostEqual(spectrum['peak'],2.3*9550*2.2/1410)
        self.assertEqual(spectrum['governing']['F1'],'прямой ход')

    def test_invalid_spectrum_never_yields_margins(self):
        for rows in ([], [level(1,.7)], [level(True,1)], [level(0,1)]):
            with self.subTest(rows=rows):
                rating = calculate(dict(gost=dict(spectrum=rows)))['rating']
                self.assertFalse(rating['available'])
                self.assertFalse(rating['complete'])
                self.assertNotIn('margins',rating)

