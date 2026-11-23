import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'src'))
from gost_manufacture import manufacture_factors, running_in
from rating import normative_rating
from test_rating import fixture


class ManufacturingTests(unittest.TestCase):
    def test_speed_boundaries_and_surface_treatment(self):
        # σHlim=800 МПа, fpb=100 мкм: до ограничения yα=20 мкм.
        for speed, y in ((4.9999,20.),(5.,16.),(10.,16.),(10.0001,8.)):
            with self.subTest(speed=speed):
                self.assertAlmostEqual(running_in(100,speed,800,True)['y'],y)
        self.assertEqual(running_in(100,5,1500,False)['y'],3.)
        self.assertAlmostEqual(running_in(8,5,1500,False)['y'],.6)

    def test_mixed_materials_and_distinct_dynamic_pitch_error(self):
        mats = [dict(sigmaHlim=800,homogeneous=True),dict(sigmaHlim=1500,homogeneous=False)]
        values = manufacture_factors({'runningInMode':'table10','dynamics':{'pitchError':8}},
                                     (12,40),7,mats,True)
        self.assertAlmostEqual(values['y'],(2.4+3)/2)
        self.assertAlmostEqual(values['yDynamics'],(1.6+.6)/2)

    def test_measured_statistics_separate_flank_and_root(self):
        # Нормированные погрешности fpbe = √(3²+4²)=5 мкм.
        cfg = dict(pitchStatisticH=1,pitchStatisticF=3,alphaEvidence='Измерения серии шестерён')
        self.assertAlmostEqual(manufacture_factors(cfg,(3,4),1,[],True)['aH'],.2)
        hard = manufacture_factors(cfg,(3,4),1,[],False)
        self.assertAlmostEqual(hard['aH'],.3)
        self.assertAlmostEqual(hard['aF'],.6)
        without_f = dict(cfg)
        del without_f['pitchStatisticF']
        self.assertEqual(manufacture_factors(without_f,(3,4),1,[],True)['aF'],1.)
        with self.assertRaises(ValueError):
            manufacture_factors(dict(cfg,aAlpha=.5),(3,4),1,[],True)
        with self.assertRaises(ValueError):
            manufacture_factors(dict(cfg,alphaEvidence=''),(3,4),1,[],True)

    def test_table10_used_in_rating_and_cannot_be_mixed_with_manual(self):
        p,c,b,t=fixture()
        p['gost']={'runningInMode':'table10','pitchStatisticH':8,'alphaEvidence':'Протокол'}
        r=normative_rating(p,c,b,t)
        self.assertTrue(r['available'],r.get('reason'))
        values = r['manufacture']
        self.assertGreater(values['y'],0)
        self.assertTrue(any(x['title']=='yα1' for x in r['trace']))
        p['gost']['yAlpha']=.5
        self.assertFalse(normative_rating(p,c,b,t)['available'])
