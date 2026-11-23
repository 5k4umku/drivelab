import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from gost_special import helical_allowable, spur_bending


def helical():
    # Восстанавливаем отношения da/db по εα1 и εα2 из примера к черт. 28.
    tw = math.tan(math.radians(22.1))
    return dict(z1=30, z2=45, db1=60, db2=90, alpha_tw=22.1,
                da1=60*math.hypot(1, tw+math.tau*.96/30),
                da2=90*math.hypot(1, tw+math.tau*.57/45),
                hp1=800, hp2=500, hb1=290, hb2=190, hv1=305, hv2=200, velocity=15)


def spur():
    c = math.cos(math.radians(20))
    return dict(z1=25, z2=50, x1=0, x2=0, module=2, alpha_tw=20, accuracy=7,
                db1=50*c, db2=100*c, da1=54, da2=104, df1=45, df2=95,
                width=25, force=3000, ka=1.25, khv=1.1, khbeta=1.3,
                kfv=1.2, kfbeta=1.25, fpb1=5, fpb2=5)


class Zones(unittest.TestCase):
    def test_figure_28_published_example(self):
        r = helical_allowable(**helical())
        self.assertAlmostEqual(r['deltaI'], 1.03, places=2)
        self.assertAlmostEqual(r['deltaII'], .93, places=2)
        self.assertEqual(r['muK2'], 1.6)
        self.assertAlmostEqual(r['hpII'], 560)
        self.assertEqual(r['hpI'], 500)
        self.assertAlmostEqual(r['HP'], math.sqrt((.96*r['deltaI']*500**2+.57*r['deltaII']*560**2)/1.53))

    def test_velocity_and_hardness_boundaries(self):
        for v, h1, h2, limit in [(14.9, 350, 350, 1.1), (15, 350, 350, 1.12),
                                (8, 351, 351, math.sqrt(1.1)), (9, 351, 351, 1)]:
            with self.subTest(v=v):
                r = helical_allowable(**dict(helical(), velocity=v, hv1=h1, hv2=h2))
                self.assertAlmostEqual(r['phiP'], limit)
        with self.assertRaisesRegex(ValueError, '350 HV'):
            helical_allowable(**dict(helical(), hv1=351))
        self.assertIsNone(helical_allowable(**dict(helical(), hv1=351, hp1=500))['phiP'])


class Phases(unittest.TestCase):
    def test_hand_calculation_for_tip_and_upper_boundary(self):
        r = spur_bending(**spur())
        self.assertAlmostEqual(r['epsilonAlpha'], 1.68316, places=5)
        self.assertAlmostEqual(r['pinion']['caPrime'], 11.9838, places=4)
        self.assertAlmostEqual(r['pinion']['cvPrime'], 17.1120, places=4)
        self.assertAlmostEqual(r['pinion']['hmu'], .87156, places=5)
        self.assertAlmostEqual(r['pinion']['tip'], 258.758, places=3)
        self.assertAlmostEqual(r['sigmaF'][0], 301.345, places=3)
        self.assertAlmostEqual(r['sigmaF'][1], 280.107, places=3)
        self.assertEqual(r['wheel']['governing'], 'single')
        r = spur_bending(**dict(spur(), fpb1=12))
        self.assertEqual(r['pinion']['governing'], 'tip')

    def test_first_approximation_and_modified_profile(self):
        r = spur_bending(**dict(spur(), profile='modified', approximation=True))
        self.assertAlmostEqual(r['pinion']['KFalphaA'], .932+.11*math.sqrt(50)/120)
        q = math.log10(25)
        self.assertAlmostEqual(r['pinion']['YFSa'], 9.003-5.908*q+2.231*q*q-.282*q**3)
        self.assertNotIn('caPrime', r['wheel'])
        exact = spur_bending(**dict(spur(), profile='modified'))
        self.assertGreater(exact['wheel']['caPrime'], 0)
        self.assertNotEqual(exact['pinion']['tip'], r['pinion']['tip'])

    def test_exchange_members(self):
        p = spur()
        for key in ('z', 'db', 'da', 'df', 'x'):
            p[key+'1'], p[key+'2'] = p[key+'2'], p[key+'1']
        self.assertEqual(spur_bending(**p)['wheel'], spur_bending(**spur())['pinion'])

    def test_domains(self):
        for edits in ({'accuracy': 9}, {'accuracy': True}, {'fpb2': -1},
                      {'db1': 40}, {'module': .5}, {'force': float('nan')}):
            with self.subTest(edits=edits), self.assertRaises(ValueError):
                spur_bending(**dict(spur(), **edits))
