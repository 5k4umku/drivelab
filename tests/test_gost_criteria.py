import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from engine import calculate
from gost_criteria import probability_lower
from gost_regimes import cdf


class CriterionTests(unittest.TestCase):
    def test_binomial_reference(self):
        self.assertAlmostEqual(probability_lower(1, 2, .95),1-.95**.5)
        self.assertAlmostEqual(probability_lower(100,100,.95),.05**.01)
        spec=dict(H=dict(passed=9,total=10,minimum=.99,confidence=.95,source='Демонстрационная серия'))
        r=calculate(dict(gost=dict(criteria=dict(trials=spec))))
        self.assertTrue(any(x['status']=='fail' and 'Испытания' in x['title'] for x in r['checks']))

    def test_life_and_site_conditions(self):
        r=calculate(dict(gost=dict(criteria=dict(lifeLimitHours=100000))))['rating']
        self.assertTrue(r.get('criteria'),r.get('reason'))
        self.assertGreater(r['criteria']['life']['hours'],0)
        cond=dict(ambientC=150,closed=True,standardRack=True,specialRules=False)
        self.assertFalse(calculate(dict(gost=dict(conditions=cond)))['rating']['available'])

    def test_table36_moments_avoid_double_cycle_weighting(self):
        r=calculate(dict(loadRegime='II',gost=dict(typicalMoments=True)))
        first=r['rating']['spectrum']['flanks'][0]
        self.assertAlmostEqual(first['TH'],r['T']*.63)
        self.assertAlmostEqual(first['TF'][1],r['T']*.72)
        self.assertAlmostEqual(first['cycles'][0],60*1410*10000)
        self.assertAlmostEqual(cdf('I',1),1.)
        self.assertAlmostEqual(cdf('IV',0),0.)

    def test_basic_equations_and_measured_properties(self):
        w=dict(label='Материал',source='Испытательный пример',E=200000,nu=.3,sigmaHlim=1000,ZN=1,ZL=1,ZR=1,Zv=1,ZW=1,ZX=1,SH=1.2,sigmaHSt=1600,SHSt=1.1,sigmaFlimb=480,YN=1,YR=1,YX=1,Ydelta=1,SF=1.5,sigmaFSt=900,SFSt=1.5,YdeltaSt=1,YdeltaStT=1,YFS=3.5)
        ks=dict(KHv=1,KHbeta=1,KHalpha=1,KFv=1,KFbeta=1,KFalpha=1)
        spec=dict(source='Проверка формул',wheels=[w,w],nominal=ks,peak=ks,Zbeta=1,Ybeta=1,Yepsilon=1)
        r=calculate(dict(geometryMode='given',gearType='spur',ratio=3,KA=1,gost=dict(basic=spec)))
        rt=r['rating']
        self.assertTrue(rt['available'],rt.get('reason'))
        self.assertAlmostEqual(rt['fs'][0],2000*r['T']/40*3.5/(30*2))
        self.assertAlmostEqual(rt['hmax']/rt['h'],2.3**.5)
        self.assertEqual(rt['fAllow'],[320,320])
        self.assertEqual(rt['hAllow'],1000/1.2)


    def test_unconfirmed_root_and_mixed_spectra_keep_reasons(self):
        for gost in (
            dict(roots=[{}, {}], design={}),
            dict(typicalMoments=True, spectrumMethod='cycles', design={},
                 spectrum=[dict(torqueRatio=1, timeFraction=1)]),
        ):
            with self.subTest(gost=gost):
                result = calculate(dict(gost=gost))
                self.assertFalse(result['rating']['available'])
                self.assertFalse(result['design']['available'])
                reasons = [item['detail'] for item in result['checks'] if item['status'] == 'pending']
                self.assertIn(result['rating']['reason'], reasons)
