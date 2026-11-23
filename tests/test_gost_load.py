import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from engine import calculate
from gost_load import face_distribution, startup_factor


class LoadTests(unittest.TestCase):
    def test_startup_bound_and_clutch(self):
        self.assertEqual(startup_factor({'machine':'fan'},1.25),1.8)
        self.assertEqual(startup_factor({'machine':'fan','softStartReduction':.25},1.5),1.5)
        self.assertEqual(startup_factor({'machine':'generator','clutchLimit':2},1.25),2)
        self.assertTrue(calculate({'gost':{'peakLoad':{'machine':'unknown'}}})['errors'])

    def test_midspan_spur_algebra(self):
        c={'d1':100,'epsilonAlpha':1.5,'epsilonBeta':0,'beta':0,'v':3,'m':4}
        spec=dict(span=120,distance=60,bearing='plain',torques='opposite',scheme=0,hv=300)
        r=face_distribution(spec,c,40,10000,'spur',7)
        psi=.4
        kq=1.6*psi**.33*49/(10000*(4-1.5)/(3*40))
        before=1+.13*psi**2+.0375*psi**2*(3+4)+kq
        self.assertAlmostEqual(r['KHbeta0'],before)
        self.assertAlmostEqual(r['KHbeta'],1+(before-1)*(1-20/(25*7**.25)))
        self.assertEqual(r['T']['Ks'],0)
        self.assertGreater(r['T']['KHbeta'],r['O']['KHbeta'])

    def test_stage_uses_different_peak_face_factor(self):
        config=dict(span=90,distance=45,bearing='ball',torques='opposite',scheme=0,hv=300)
        r=calculate(dict(gost=dict(face27=config,peakLoad=dict(machine='fan'))))
        self.assertEqual(r['input']['startup'],1.8)
        rt=r['rating']
        self.assertTrue(rt['available'],rt.get('reason'))
        self.assertEqual(rt['KHalpha'],1)
        self.assertAlmostEqual(rt['KHbeta'],rt['face27']['KHbeta'])
        self.assertTrue(any('торца O' in s['title'] for s in r['trace']))
        self.assertFalse(calculate(dict(gost=dict(face27={**config,'distance':1000})))['rating']['available'])

    def test_shifted_drawing_propagates_to_assembly_and_force(self):
        from assembly import from_single,calculate_assembly
        p=from_single()
        p['stages'][0]['input'].update(geometryMode='given',gearType='spur',ratio=3,x1=.3,x2=-.1)
        a=calculate_assembly(p)
        self.assertFalse(a['errors'])
        result=a['stages'][0]['result']
        c=result['chosen']
        self.assertTrue(result['rating']['available'],result['rating'].get('reason'))
        self.assertGreater(c['a'],c['aReference'])
        self.assertAlmostEqual(c['a'],(c['dw1']+c['dw2'])/2)
        self.assertAlmostEqual(c['Ft']*c['dw1']/2000,result['T'])

