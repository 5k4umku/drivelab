"""Boundary and physical-invariant checks for the restricted GOST profile."""
import copy
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from rating import bending_life, contact_life, normative_rating
from engine import DEFAULTS


def fixture(gear_type='helical'):
    p = copy.deepcopy(DEFAULTS)
    p.update(gearType=gear_type, alpha=20, treatment1='У', treatment2='У',
             rowName1='У785', rowName2='У685')
    beta = 0 if gear_type == 'spur' else math.radians(20)
    m, z1, z2 = 2., 25, 157
    d1, d2 = m*z1/math.cos(beta), m*z2/math.cos(beta)
    at = math.atan(math.tan(math.radians(20))/math.cos(beta))
    a = (d1+d2)/2
    da1, da2 = d1+2*m, d2+2*m
    db1, db2 = d1*math.cos(at), d2*math.cos(at)
    ea = (math.sqrt(da1**2-db1**2)/2 + math.sqrt(da2**2-db2**2)/2 - a*math.sin(at))/(math.pi*m/math.cos(beta)*math.cos(at))
    c = dict(m=m, z1=z1, z2=z2, beta=math.degrees(beta), alphaT=math.degrees(at),
             d1=d1,d2=d2,da1=da1,da2=da2,epsilonAlpha=ea,u=z2/z1,
             v=math.pi*d1*p['speed']/60000)
    return p,c,32.,9550*p['power']/p['speed']


class LifeBoundaryTests(unittest.TestCase):
    def test_contact_knee_and_limits(self):
        self.assertEqual(contact_life(1e7,1e7),1)
        self.assertAlmostEqual(contact_life(1e7,2e7),2**(-1/20))
        self.assertEqual(contact_life(1e7,1e30),.75)
        self.assertEqual(contact_life(1e7,1),2.6)
        self.assertEqual(contact_life(1e7,1,False),1.8)

    def test_bending_surface_and_homogeneous_caps_differ(self):
        self.assertEqual(bending_life(1,6),4)
        self.assertEqual(bending_life(1,9),2.5)
        self.assertEqual(bending_life(1e9,6),1)

    def test_invalid_cycles_rejected(self):
        with self.assertRaises(ValueError): contact_life(1e7,0)
        with self.assertRaises(ValueError): bending_life(-1)


class PhysicalTests(unittest.TestCase):
    def test_independent_spur_hand_case(self):
        # Hand worksheet: m=2, z=20/40, d=40/80, b=20, T=10, v=1.
        # No pitch error => KHalpha=KFalpha=1; no face skew => Kbeta=1.
        # Ft=500; wHv=.06*4.7*sqrt(30); wFv=.16*4.7*sqrt(30).
        # Frozen values were evaluated independently, without importing rating.
        p=copy.deepcopy(DEFAULTS)
        p.update(gearType='spur',alpha=20,treatment1='У',treatment2='У',
                 rowName1='У785',rowName2='У685',speed=60000/(40*math.pi),
                 KA=1,KHbeta=1,KFbeta=1,fpb1=0,fpb2=0,accuracy=7)
        c=dict(m=2,z1=20,z2=40,beta=0,alphaT=20,d1=40,d2=80,
               da1=44,da2=84,epsilonAlpha=1.6351859635714583,v=1,u=2)
        r=normative_rating(p,c,20,10)
        self.assertTrue(r['available'],r.get('reason'))
        self.assertAlmostEqual(r['KHv'],1.0617831044865826,12)
        self.assertAlmostEqual(r['KFv'],1.1647549452975539,12)
        self.assertAlmostEqual(r['sigmaH'],419.8472003306685,9)
        self.assertAlmostEqual(r['sigmaF'][0],60.130474050986216,9)
        self.assertAlmostEqual(r['sigmaF'][1],55.325859901633805,9)

    def test_invalid_imported_configuration_returns_reason(self):
        for cfg in ([],None,{'aAlpha':True},{'KHbeta':float('nan')},
                    {'yield1':float('inf')},{'peakCycles':'100'},
                    {'peakCycles':1.5},{'surfaceConfirmed':'yes'},
                    {'peakProbabilityFactor':0},{'mystery':1}):
            with self.subTest(cfg=cfg):
                p,c,b,t=fixture()
                p['gost']=cfg
                r=normative_rating(p,c,b,t)
                self.assertFalse(r['available'])
                self.assertTrue(r['reason'])
        p,c,b,t=fixture()
        c['d1']=True
        self.assertFalse(normative_rating(p,c,b,t)['available'])

    def test_geometry_and_width_must_match(self):
        for key,value in [('alphaT',-20),('d1',1),('u',5),('epsilonAlpha',2),('epsilonBeta',100)]:
            p,c,b,t=fixture()
            c[key]=value
            self.assertFalse(normative_rating(p,c,b,t)['available'],key)

    def test_peak_repeat_boundary(self):
        p,c,b,t=fixture()
        p['gost']={'peakCycles':999}
        self.assertEqual(normative_rating(p,c,b,t)['checks'][-1]['status'],'pass')
        p['gost']['peakCycles']=1000
        self.assertEqual(normative_rating(p,c,b,t)['checks'][-1]['status'],'fail')

    def test_trace_contains_numeric_dependencies(self):
        r=normative_rating(*fixture())
        titles={item['title'] for item in r['trace']}
        for title in ('εα','εβ','εγ','βb','c′','cγ','NHE1','NFE2','KHα добавка A','KHαmax','σFPmax1'):
            self.assertIn(title,titles)
        self.assertTrue(all(item['substitution'] for item in r['trace']))
        self.assertFalse(any('По фактической' in item['substitution'] for item in r['trace']))

    def test_spur_one_pair_root_model(self):
        r=normative_rating(*fixture('spur'))
        self.assertTrue(r['available'])
        self.assertEqual(r['Ybeta'],1)
        self.assertEqual(r['Yepsilon'],1)
        self.assertEqual(r['KFalpha'],1)

    def test_herringbone_equal_halves_match_a_single_half(self):
        p,c,b,t=fixture()
        single=normative_rating(p,c,b,t)
        p['gearType']='herringbone'
        twin=normative_rating(p,c,2*b,2*t)
        self.assertAlmostEqual(single['sigmaH'],twin['sigmaH'])
        self.assertEqual(single['sigmaF'],twin['sigmaF'])
        self.assertAlmostEqual(single['epsilonBeta'],twin['epsilonBeta'])

    def test_peak_count_does_not_silently_pass(self):
        r=normative_rating(*fixture())
        self.assertFalse(r['complete'])
        self.assertEqual(r['checks'][-1]['status'],'pending')

    def test_maximum_moment_increases_peak_stresses(self):
        p,c,b,t=fixture()
        r1=normative_rating(p,c,b,t)
        p['startup']*=2
        r2=normative_rating(p,c,b,t)
        self.assertGreater(r2['sigmaHmax'],r1['sigmaHmax'])
        self.assertAlmostEqual(r2['sigmaFmax'][0],2*r1['sigmaFmax'][0])
        self.assertEqual(r1['sigmaH'],r2['sigmaH'])

    def test_resonance_and_unsupported_geometry_are_not_green(self):
        p,c,b,t=fixture()
        c['v']=24
        c['z1']=100
        self.assertFalse(normative_rating(p,c,b,t)['available'])
        p,c,b,t=fixture()
        p['alpha']=25
        self.assertFalse(normative_rating(p,c,b,t)['available'])

    def test_load_increases_working_stresses(self):
        p,c,b,t=fixture()
        r1=normative_rating(p,c,b,t)
        r2=normative_rating(p,c,b,2*t)
        self.assertGreater(r2['sigmaH'],r1['sigmaH'])
        self.assertGreater(r2['sigmaF'][0],r1['sigmaF'][0])


if __name__=='__main__': unittest.main()
