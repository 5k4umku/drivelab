import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from gost_dynamics import resonance_state, resonant_factor, subcritical_forces
from gost_geometry import external_geometry
from rating import normative_rating
from test_rating import fixture


class DynamicTests(unittest.TestCase):
    def setUp(self):
        self.g = external_geometry(2, 30, 60, 0, 20, 1000)
        self.cfg = dict(resonanceRpm=1000, pitchError=8, profileError=5)

    def factor(self, speed, overlap, cfg=None):
        cfg = self.cfg if cfg is None else cfg
        state = resonance_state(dict(self.g, speed=speed), 10, cfg)
        return resonant_factor(state, cfg, overlap, 10, 20, 2000, 1., 2, [97*18.45]*2)

    def test_resonant_and_supercritical_reference_values(self):
        # c′=10, Ft/b=100, yα=2: Bp=0,6; Bf=0,3; Ca=1,5; BK=0,85.
        for n in (850, 1000, 1150):
            with self.subTest(n=n):
                self.assertAlmostEqual(self.factor(n, 1.4)['Kv'], 2.059)
        self.assertAlmostEqual(self.factor(1500, 1.4)['Kv'], 1.173)
        self.assertAlmostEqual(self.factor(1325, 1.4)['Kv'], (2.059 + 1.173)/2)
        before = resonance_state(dict(self.g, speed=849.9999), 10, self.cfg)
        self.assertEqual(before['zone'], 'subcritical')

    def test_overlap_boundaries_and_high_overlap_external_values(self):
        self.assertEqual(self.factor(1500,1.5)['Cv']['Cv7'], .75)
        self.assertEqual(self.factor(1500,1.96)['Cv']['Cv7'], .875)
        self.assertTrue(self.factor(1500,2)['Kv'] > 1)
        with self.assertRaisesRegex(ValueError, 'Cv5, Cv6'):
            self.factor(1500,2.5)
        cfg = dict(self.cfg, coefficients={'Cv5':.31, 'Cv6':.29}, coefficientSource='Паспорт стенда')
        self.assertAlmostEqual(self.factor(1500,2.5,cfg)['Kv'], 1 + .31*.6 + .29*.3)
        with self.assertRaisesRegex(ValueError, 'Cv2, Cv4'):
            self.factor(1325, 2.5, cfg)

    def test_specified_moments_use_kilogram_square_millimetres(self):
        # I₁/rb₁²=2 кг, I₂/rb₂²=3 кг: приведённая масса 1,2 кг.
        cfg = {f'inertia{i}': k * (self.g[f'db{i}']/2)**2 for i,k in ((1,2), (2,3))}
        state = resonance_state(self.g,10,cfg)
        self.assertAlmostEqual(state['reducedMassKg'],1.2)
        cg = 10 * (.75*self.g['epsilonAlpha'] + .25)
        omega = math.sqrt(1e6*cg*20/1.2)
        self.assertAlmostEqual(state['nE1'], omega * 60 / (2*math.pi*30))
        self.assertLess(resonance_state(self.g,10,dict(cfg,attachedRatio=3))['nE1'],state['nE1'])

    def test_added_inertia_spur_modification_and_cap(self):
        default = subcritical_forces(2,7,True,False,False,100,2,2)
        modified = subcritical_forces(2,7,True,False,True,100,2,2,gamma=4)
        self.assertAlmostEqual(modified['massFactor'], 2.5)
        self.assertAlmostEqual(modified['wH']/default['wH'], 2.5*.04/.06)
        capped = subcritical_forces(2,7,False,False,False,10000,2,25,gamma=40)
        self.assertEqual(capped['wF'], capped['limit'])

    def test_bad_inputs(self):
        for cfg in ({'inertia1':12}, {'resonanceRpm':0}, {'pitchError':True},
                    {'inertia1':1,'inertia2':2,'resonanceRpm':500},
                    {'coefficients':{'Cv2':.1}}, {'coefficients':{'Cv9':.4}},
                    {'resonanceRpm':float('nan')}, {'abc':3}):
            with self.subTest(cfg=cfg), self.assertRaises(ValueError):
                resonance_state(self.g,10,cfg)
        with self.assertRaisesRegex(ValueError, 'приработка|Приработка'):
            self.factor(1500,1.4,dict(self.cfg,pitchError=1))

    def test_rating_consumes_measured_frequency_and_peak_force(self):
        p,c,b,t = fixture('spur')
        p['gost'] = {'dynamics':dict(self.cfg,resonanceRpm=p['speed'])}
        r = normative_rating(p,c,b,4*t)
        self.assertTrue(r['available'],r.get('reason'))
        self.assertEqual(r['dynamics']['zone'],'resonant')
        self.assertEqual(r['KHv'],r['KFv'])
        self.assertNotEqual(r['KHv'],r['dynamics']['peak']['Kv'])
        del p['gost']['dynamics']['profileError']
        self.assertFalse(normative_rating(p,c,b,4*t)['available'])
