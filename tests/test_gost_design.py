"""Проверки обеих зависимостей п. 5.2.3 и графиков пп. 5.1.4, 5.2.5."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'src'))
from gost_design import chart_factor, project_design


class DesignTests(unittest.TestCase):
    def setUp(self):
        self.p = dict(gearType='spur',psiBd=.8,KHbeta=1.2,KFbeta=1.3,sigmaH1=600,
                      sigmaH2=600,sigmaF1=500,sigmaF2=500,SH=1.2,NHG1=10,NHG2=20)
        self.c = dict(u=2,z1=20,aW=75)
        self.rating = dict(available=True,epsilonBeta=0,YN=[1.,1.],ZN=[1.,1.],YFS=[4.,4.])

    def calculate(self, **cfg):
        return project_design(dict(self.p,gost={'design':cfg}),self.c,25,20,self.rating)

    def test_four_spur_dimensions(self):
        result = self.calculate()
        self.assertTrue(result['available'], result.get('reason'))
        self.assertEqual(result['HP'],450)
        self.assertEqual(result['FP1'],200)
        for key,v in dict(dw1=46.63942855,aW=71.39135373,moduleByWidth=1.64593428,moduleByCenter=.896).items():
            self.assertAlmostEqual(result[key],v)

    def test_helical_both_overlap_ranges_and_cap(self):
        self.p['gearType']='helical'
        self.rating['epsilonBeta']=1
        low=self.calculate()
        self.assertEqual(low['HP'],405.)
        self.assertEqual(low['cases'][0]['Km'],12.5)
        self.assertEqual(low['cases'][0]['Kma'],1100)
        self.rating['epsilonBeta']=1.00001
        high=self.calculate()
        self.assertEqual(high['cases'][0]['Km'],11.2)
        self.assertEqual(high['cases'][0]['Kma'],850)
        self.assertLess(high['moduleByCenter'],low['moduleByCenter'])
        self.p['sigmaH2']=200
        self.assertAlmostEqual(self.calculate()['HP'],1.23*150)

    def test_reversal_smaller_allowable_and_width_ratio_conversion(self):
        r=self.calculate(reversing=True,psiBa=1.6/3)
        self.assertAlmostEqual(r['psiBd'],.8)
        self.assertEqual(r['FP1'],150)
        self.assertAlmostEqual(self.calculate()['moduleByCenter']/r['moduleByCenter'],.75)
        self.assertFalse(self.calculate(psiBd=.4,psiBa=.2)['available'])

    def test_all_chart_curves_in_both_hardness_groups(self):
        for criterion in ('H','F'):
            for hard in (False,True):
                at_point=[chart_factor(criterion,hard,i,.4) for i in range(1,8)]
                self.assertEqual(at_point,sorted(at_point,reverse=True))
                for i in range(1,8):
                    self.assertAlmostEqual(chart_factor(criterion,hard,i,.3),
                        (chart_factor(criterion,hard,i,.2)+chart_factor(criterion,hard,i,.4))/2)
        self.assertAlmostEqual(chart_factor('H',False,3,.8),1.12)
        self.assertAlmostEqual(chart_factor('F',True,7,1.60),1.30)
        r=self.calculate(scheme=4,hardPair=False)
        self.assertTrue(r['available'])
        self.assertGreater(r['KFbeta'],r['KHbeta'])
        self.assertFalse(self.calculate(scheme=1,hardPair=True,psiBd=.9)['available'])
        self.assertFalse(self.calculate(scheme=True,hardPair=True)['available'])

    def test_separate_contact_and_bending_spectrum_loads(self):
        self.rating['spectrum']={'flanks':[
            dict(sign=1,cycles=[1e7,5e6],TH=12,TF=[14,14],YN=[1,1]),
            dict(sign=-1,cycles=[2e7,1e7],TH=24,TF=[10,10],YN=[1,1])]}
        r=self.calculate()
        self.assertTrue(r['available'],r.get('reason'))
        self.assertEqual(r['FP1'],150)
        self.assertEqual(r['cases'][0]['T2H'],24)
        self.assertEqual(r['cases'][0]['T2F'],28)
        self.assertEqual(r['aW'],r['cases'][1]['aW'])
        self.assertEqual(r['moduleByWidth'],r['cases'][0]['moduleByWidth'])

    def test_preliminary_sizing_does_not_require_verified_dynamic_load(self):
        from test_rating import fixture
        from rating import normative_rating
        p,c,b,t = fixture()
        c['aW']=(c['d1']+c['d2'])/2
        before=project_design(p,c,b,t,normative_rating(p,c,b,t))
        p['gost']={'dynamics':{'resonanceRpm':p['speed']}}
        incomplete=normative_rating(p,c,b,t)
        self.assertFalse(incomplete['available'])
        after=project_design(p,c,b,t,incomplete)
        self.assertTrue(after['available'],after.get('reason'))
        for key in ('aW','dw1','moduleByWidth','moduleByCenter'):
            self.assertAlmostEqual(after[key],before[key])
