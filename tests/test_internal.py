"""Внутренняя пара: номинальная геометрия, силы и область применимости."""
import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from engine import DEFAULTS, calculate
from assembly import from_single, new_shaft, calculate_assembly


def inputs(**patch):
    return {**DEFAULTS,'meshType':'internal','gearType':'spur','ratio':3,**patch}


class InternalTests(unittest.TestCase):
    def test_gost_table_2_zero_shift_reference(self):
        r=calculate(inputs()); self.assertEqual(r['errors'],[])
        c=r['chosen']
        for key,value in dict(m=2,z1=20,z2=60,a=40,b=30,d1=40,d2=120,da1=44,da2=116.8,df1=35,df2=125,outerDiameter=145,n2=470).items():
            self.assertAlmostEqual(c[key],value,msg=key)
        self.assertAlmostEqual(c['Ft'],745.0354609929078)
        self.assertAlmostEqual(c['Fr'],745.0354609929078*math.tan(math.pi/9))
        self.assertEqual(c['Fa'],0)
        self.assertFalse(r['rating']['available'])
        self.assertIsNone(c['contactMargin'])
        self.assertEqual(r['status'],'pending')
        self.assertTrue(any('Интерференция' in x['title'] and x['status']=='pending' for x in r['checks']))

    def test_helical_and_herringbone_geometry(self):
        h=calculate(inputs(gearType='helical'))['chosen']
        v=calculate(inputs(gearType='herringbone'))['chosen']
        self.assertAlmostEqual(h['a'],40/math.cos(math.pi/12))
        self.assertAlmostEqual(h['Fa'],h['Ft']*math.tan(math.pi/12))
        self.assertEqual(v['Fa'],0)
        self.assertAlmostEqual(v['epsilonBeta'],h['epsilonBeta']/2)
        self.assertAlmostEqual(v['FaLeft'],-v['FaRight'])

    def test_unbalanced_herringbone_has_residual_thrust(self):
        c=calculate(inputs(gearType='herringbone',gost={'halfLoadShare':.6}))['chosen']
        self.assertAlmostEqual(c['Fa'],c['FaLeft']+c['FaRight'])
        self.assertGreater(c['Fa'],0)

    def test_invalid_geometry_is_rejected(self):
        for patch in [dict(manualZ1=60),dict(manualZ2=18),dict(manualZ1=20.2),dict(manualModule=0),dict(manualWidth=0),dict(ringRim=0),dict(gearType='helical',manualBeta=50),dict(manualZ2=1001)]:
            with self.subTest(patch=patch):self.assertTrue(calculate(inputs(**patch))['errors'])

    def test_internal_rotation_and_common_contact_point(self):
        p=from_single(inputs(gearType='helical')); r=calculate_assembly(p)
        self.assertEqual(r['errors'],[])
        self.assertGreater(r['shafts'][1]['signedSpeed'],0)
        a,b=r['gears']
        self.assertAlmostEqual(a['x']+a['offset'][0],b['x']+b['offset'][0])
        self.assertAlmostEqual(a['y']+a['offset'][1],b['y']+b['offset'][1])
        for i in range(3):self.assertAlmostEqual(a['force'][i],-b['force'][i])
        torque=lambda g:(g['offset'][0]*g['force'][1]-g['offset'][1]*g['force'][0])/1000
        self.assertAlmostEqual(torque(a),-r['shafts'][0]['torque'])
        self.assertGreater(torque(b),0)
        self.assertFalse(any('венец ступени 1 и вал 1' in x for x in r['collisions']))
        for s in r['shafts']:self.assertLess(max(map(abs,s['forceResidual']+s['momentResidual'])),1e-6)

    def test_mixed_train_directions(self):
        p=from_single(inputs()); p['stages'].append(dict(input={**DEFAULTS,'ratio':3},angle=30,axial=None,hand='right'));p['shafts'].append(new_shaft())
        r=calculate_assembly(p); self.assertFalse(r['errors'])
        self.assertGreater(r['shafts'][1]['signedSpeed'],0)
        self.assertLess(r['shafts'][2]['signedSpeed'],0)
        self.assertAlmostEqual(r['outputSpeed'],p['speed']/r['totalRatio'])

    def test_external_table_does_not_rate_internal_mesh(self):
        p=from_single(inputs(faceMode='seminar',psiBd=2))
        r=calculate_assembly(p);self.assertFalse(r['errors'])
        self.assertNotIn('faceSelection',r['stages'][0])
        self.assertFalse(r['stages'][0]['result']['rating']['available'])

if __name__=='__main__':unittest.main()
