import copy
import math
import unittest

from test_rating import fixture
from gost_spectrum import stage_rating


class StagedLoading(unittest.TestCase):
    def run_spectrum(self, method, rows, multiplier=8, **controls):
        p,c,b,t=fixture()
        p.update(startup=1,autoTables=False,KA=1,life=20000,**controls)
        p['gost']={'spectrum':rows,'spectrumMethod':method}
        return stage_rating(p,c,b,t*multiplier)

    def test_constant_control_agrees_for_damaging_stress_and_maxima(self):
        rows=[dict(torqueRatio=1,timeFraction=1)]
        p,c,b,t=fixture()
        p.update(startup=1,autoTables=False,KA=1,muF=1,muH=1,life=20000)
        normal=stage_rating(p,c,b,t*22)
        r=self.run_spectrum('stresses',rows,22)
        self.assertTrue(r['available'],r.get('reason'))
        for k in ('H','F1','F2','Hmax','Fmax1','Fmax2'):
            self.assertAlmostEqual(r['margins'][k],normal['margins'][k],places=8)

    def test_reference_comes_from_sustained_load_not_short_peak(self):
        rows=[dict(torqueRatio=1,timeFraction=.99999),dict(torqueRatio=2,timeFraction=.00001)]
        r=self.run_spectrum('cycles',rows,12)
        self.assertTrue(r['available'],r.get('reason'))
        self.assertEqual(r['history']['members'][0]['contact']['referenceIndex'],0)
        self.assertEqual(r['history']['members'][0]['contact']['overloads'],[1])
        self.assertIn('Hover2',r['margins'])
        self.assertEqual(r['history']['peakIndexes']['Hmax'],1)
        stress=self.run_spectrum('stresses',rows,12)
        self.assertNotIn(1,stress['history']['members'][0]['contact']['included'])
        self.assertEqual(stress['history']['peakIndexes']['Hmax'],1)

    def test_undefinable_fatigue_does_not_hide_peak(self):
        r=self.run_spectrum('stresses',[dict(torqueRatio=1,timeFraction=1)],.05)
        self.assertTrue(r['available'],r.get('reason'))
        self.assertIsNone(r['margins']['F1'])
        self.assertTrue(math.isfinite(r['margins']['Hmax']))
        self.assertTrue(r['mandatoryPending'])
        self.assertFalse(r['complete'])

    def test_frequency_changes_stresses_and_cycles(self):
        rows=[dict(torqueRatio=1,timeFraction=.5,speedRatio=.5),dict(torqueRatio=1,timeFraction=.5,speedRatio=1)]
        r=self.run_spectrum('stresses',rows,12)
        a,b=r['history']['levels']
        self.assertEqual(2*a['cycles'],b['cycles'])
        self.assertGreater(b['sigmaH'],a['sigmaH'])
        high=copy.deepcopy(rows)
        high[1]['speedRatio']=100
        self.assertFalse(self.run_spectrum('stresses',high)['available'])

    def test_inactive_stop_does_not_create_load_cycles(self):
        r=self.run_spectrum('cycles',[dict(torqueRatio=0,speedRatio=0,timeFraction=.2),
                                      dict(torqueRatio=.8,timeFraction=.8)])
        self.assertTrue(r['available'],r.get('reason'))
        self.assertEqual([x['id'] for x in r['history']['levels']],[2])

    def test_invalid_speed_rejected(self):
        for value in (0,-1,True,float('nan')):
            r=self.run_spectrum('stresses',[dict(torqueRatio=1,timeFraction=1,speedRatio=value)])
            self.assertFalse(r['available'],value)

    def test_equal_reverse_cycles_uses_separate_flank_fatigue(self):
        rows=[dict(torqueRatio=1,timeFraction=.5),dict(torqueRatio=-1,timeFraction=.5)]
        r=self.run_spectrum('cycles',rows,12)
        self.assertTrue(r['available'],r.get('reason'))
        self.assertEqual(r['history']['YA'],dict(forward=[.65,.65],reverse=[.65,.65]))
        self.assertEqual(r['history']['originalRows'],dict(forward=[1],reverse=[2]))
        p,c,b,t=fixture()
        p.update(startup=1,autoTables=False,KA=1,life=10000,muF=1,muH=1)
        p['gost']=dict(spectrum=[dict(torqueRatio=1,timeFraction=1)],spectrumMethod='cycles')
        single=stage_rating(p,c,b,t*12)
        self.assertAlmostEqual(r['fp'][0],.65*single['fp'][0])
        self.assertAlmostEqual(r['hp'][0],single['hp'][0])

    def test_reversing_equivalent_stresses_require_tested_ratios(self):
        p,c,b,t=fixture()
        rows=[dict(torqueRatio=.8,timeFraction=.5),dict(torqueRatio=-1,timeFraction=.5)]
        p.update(startup=1,autoTables=False,KA=1,life=20000)
        p['gost']=dict(spectrum=rows,spectrumMethod='stresses')
        self.assertFalse(stage_rating(p,c,b,t*12)['available'])
        p['gost']['reverseYA']=dict(forward=[.7,.74],reverse=[.65,.75],source='Численный контроль независимых коэффициентов')
        r=stage_rating(p,c,b,t*12)
        self.assertTrue(r['available'],r.get('reason'))
        self.assertEqual(r['history']['YA']['reverse'],[.65,.75])
