import copy
import unittest

from test_rating import fixture, normative_rating
from gost_materials import material_properties


def steel(row, **inputs):
    return dict(label='Опытный венец',row=row,evidence='Контрольная карта для проверки формул',
                blank='forged',grinding='none',rootTreatment='none', **inputs)


def annex11():
    # Табл. 39 подставляет 59 HRCэ для шестерни, хотя табл. 37 указывает 58.
    # Параметры процесса, отсутствующие в примере, заданы как условия теста.
    pinion = steel('15.1', hrc=59,hb=590,hv=680,coreHrc=34,carbon=.85,nitrogen=.2,
                   technologyCompliant=True,smoothSpectrum=True,darkPhaseAbsent=True)
    wheel = steel('17.4', hrc=50,hb=470,hv=515,rootHrc=50,coreHrc=30,technologyCompliant=True)
    return [pinion,wheel]


class MaterialPassports(unittest.TestCase):
    def test_annex11_table39_table40(self):
        pair = [material_properties(a,5) for a in annex11()]
        self.assertEqual([p['sigmaHlim'] for p in pair],[1357,1050])
        self.assertEqual([p['sigmaFlimb0'] for p in pair],[1000,580])
        self.assertEqual([p['SF'] for p in pair],[1.55,1.7])
        self.assertEqual([p['SH'] for p in pair],[1.2,1.2])
        self.assertEqual(pair[0]['NHlim'],120e6)
        self.assertAlmostEqual(pair[1]['NHlim']/1e6,77.6,delta=.3)
        self.assertEqual([p['staticBase'] for p in pair],[2500,1800])
        self.assertEqual([p['hpmax'] for p in pair],[None,2200])
        self.assertEqual([p['qF'] for p in pair],[9,None])

    def test_process_departures_are_applied_once(self):
        a,b = annex11()
        a.update(caseDepth=.2,grainSize=4,coreHrc=27)
        b.update(noFerrite=False)
        self.assertEqual(material_properties(a,5)['YT'],.75)
        self.assertEqual(material_properties(b,5)['YT'],.70)
        a['grinding']='finish'
        a['goodGrinding']=False
        p=material_properties(a,5)
        self.assertEqual(p['qF'],6)
        self.assertAlmostEqual(p['Yg'],.7*.75)
        self.assertEqual(p['YgSt'],.95)

    def test_nitriding_contact_limits(self):
        sample=steel('16.6',hb=550,hv=650,flankRa=1.25,contactPatternGrade=6,
                     coreHrc=29,technologyCompliant=False)
        p=material_properties(sample,5)
        self.assertEqual(p['sigmaFlimb0'],638)
        self.assertEqual((p['sigmaHlim'],p['hpmax'],p['staticBase']),(1050,1950,1800))
        self.assertEqual((p['YT'],p['gammaA']),(.8,.1))
        for key,value in [('hv',751),('flankRa',1.26),('contactPatternGrade',7)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                material_properties(dict(sample, **{key:value}),5)

    def test_grade_boundaries_and_invalid_certificates(self):
        a,b=annex11()
        for specimen in (dict(a,hrc=56),dict(a,carbon=.4),dict(a,darkPhaseAbsent=False),
                         dict(b,rootHrc=47),dict(b,evidence=''),dict(b,technologyCompliant='true'),
                         dict(b,hrc=True),dict(b,table19Inapplicable=True)):
            with self.subTest(row=specimen['row']), self.assertRaises(ValueError):
                material_properties(specimen,5)

    def test_allowables_use_new_passports_and_pending_peak(self):
        p,c,b,t=fixture()
        p.update(muH=1,muF=1,life=50000)
        p['gost']=dict(materials=annex11(),peakCycles=10,peakProbabilityFactorConfirmed=True,
                       surfaceConfirmed=True,faceFactorsConfirmed=True)
        result=normative_rating(p,c,b,t)
        self.assertTrue(result['available'],result.get('reason'))
        self.assertIsNone(result['margins']['Hmax'])
        self.assertTrue(result['mandatoryPending'])
        self.assertFalse(result['complete'])
        p['gost']['materials'][1]['row']='неизвестная строка'
        self.assertFalse(normative_rating(p,c,b,t)['available'])

    def test_forging_and_rolled_blank_are_independent(self):
        p,c,b,t=fixture()
        one=steel('16.1',hb=280,hv=292,yieldStrength=685)
        two=dict(one,blank='rolled')
        p['gost']=dict(materials=[one,two])
        result=normative_rating(p,c,b,t)
        self.assertTrue(result['available'],result.get('reason'))
        self.assertEqual(result['hpmax'],[2.8*685]*2)
        self.assertAlmostEqual(result['fpmax'][1],6.5*280*(1.05-.000125*c['d2'])/(.9*1.75))
        self.assertEqual([m['YZ'] for m in result['materialProperties']],[1,.9])

    def test_zonal_contact_and_two_spur_phases_reach_rating(self):
        p,c,b,t=fixture()
        mat=steel('16.1',hb=280,hv=292,yieldStrength=685)
        p['gost']=dict(materials=[mat,copy.copy(mat)],refineContact=True)
        result=normative_rating(p,c,b,t)
        self.assertTrue(result['available'],result.get('reason'))
        self.assertEqual(result['HP'],result['zonalContact']['HP'])
        p,c,b,t=fixture('spur')
        p['gost']=dict(refineBending=True)
        result=normative_rating(p,c,b,t)
        self.assertTrue(result['available'],result.get('reason'))
        self.assertEqual(result['sigmaF'],result['spurBending']['sigmaF'])
