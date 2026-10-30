"""Табличные границы, независимые численные примеры и связь с компоновкой."""
import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from engine import calculate, DEFAULTS, material_pair
from assembly import from_single, calculate_assembly, new_shaft
from coefficients import prepare, t5_factor, layout_case, face_factors

class TableTests(unittest.TestCase):
    def test_regime_and_reverse_are_independent(self):
        p,trace=prepare({**DEFAULTS,'loadRegime':'IV','loadDirection':'reversing'})
        self.assertEqual((p['muH'],p['muF'],p['YA']),(.125,.038,.65))
        p,_=prepare({**DEFAULTS,'loadRegime':'0','loadDirection':'oneway'})
        self.assertEqual((p['muH'],p['muF'],p['YA']),(1,1,1))
        self.assertTrue(all(t['source'] and t['substitution'] for t in trace))

    def test_external_load_table_rows_and_columns(self):
        p,_=prepare({**DEFAULTS,'autoKA':True,'driverClass':2,'machineClass':0})
        self.assertEqual(p['KA'],1.25) # скан, табл.21: не ошибочное OCR «1.23»
        p,_=prepare({**DEFAULTS,'autoKA':True,'driverClass':0,'machineClass':3})
        self.assertEqual(p['KA'],1.75)

    def test_t5_exact_interpolation_and_missing_cells(self):
        self.assertEqual(t5_factor(.6,'console-ball')['value'],1.27)
        self.assertAlmostEqual(t5_factor(.5,'console-ball')['value'],1.22)
        self.assertIsNone(t5_factor(.9,'console-ball'))
        self.assertIsNone(t5_factor(.39,'both-offset'))
        self.assertIsNone(t5_factor(1.61,'both-offset'))

    def test_position_classifier(self):
        center=dict(A={'z':-50},B={'z':50},bearing='ball')
        offset=dict(A={'z':-50},B={'z':100},bearing='roller')
        self.assertEqual(layout_case(0,[center,center],10),'symmetric-axial')
        self.assertEqual(layout_case(0,[offset,center],0),'pinion-offset')
        self.assertEqual(layout_case(0,[center,offset],0),'wheel-offset')
        self.assertEqual(layout_case(120,[center,offset],0),'console-ball')

    def test_t5_follows_real_supports_and_updates_design(self):
        p=from_single({**DEFAULTS,'faceMode':'seminar'})
        a=calculate_assembly(p)
        self.assertFalse(a['errors'])
        self.assertEqual(a['stages'][0]['faceSelection']['value'],1.27)
        p['shafts']=[new_shaft(),new_shaft()]
        b=calculate_assembly(p)
        self.assertFalse(b['errors'])
        self.assertEqual(b['stages'][0]['faceSelection']['value'],1.03)
        self.assertLess(b['stages'][0]['result']['ap'],a['stages'][0]['result']['ap'])

    def test_custom_material_is_not_overwritten(self):
        p={**DEFAULTS,'materialMode':'custom','material1':'Моя сталь','sigmaH1':700,'yield1':800}
        self.assertEqual(material_pair(p)['sigmaH1'],700)
        r=calculate(p)
        self.assertTrue(r['rating']['available'])
        self.assertEqual(r['input']['gost']['yield1'],800)

    def test_grade_changes_automatic_pitch_error(self):
        a=calculate({**DEFAULTS,'accuracy':6,'speed':400})
        b=calculate({**DEFAULTS,'accuracy':9,'speed':400})
        self.assertLess(a['rating']['KHv'],b['rating']['KHv'])
        self.assertLess(a['rating']['h'],b['rating']['h'])

    def test_spur_contact_distribution_is_one(self):
        r=calculate({**DEFAULTS,'gearType':'spur'})
        self.assertEqual(r['rating']['KHalpha'],1)
        self.assertEqual(r['rating']['KFalpha'],1)

    def test_reversal_reduces_bending_allowable_only(self):
        a=calculate({**DEFAULTS,'loadDirection':'oneway'})
        b=calculate({**DEFAULTS,'loadDirection':'reversing'})
        # В этом примере выбранная геометрия одинакова; отношение σFP равно YA.
        self.assertEqual(a['chosen']['z1'],b['chosen']['z1'])
        self.assertAlmostEqual(b['rating']['fp'][0]/a['rating']['fp'][0],.65)
        self.assertAlmostEqual(b['rating']['hAllow'],a['rating']['hAllow'])

class FormulaTests(unittest.TestCase):
    def test_independent_face_factor_arithmetic(self):
        v=face_factors(width=40,diameter=100,module=2,ea=1.5,beta=.2,at=math.acos(.9),force=2000,ka=1,khv=1.1,stiffness=20,zeps=.8,velocity=12,hv=300,deviation=5,torque_side='input')
        # KHβ0=1+1440/1408+.14*.16; KHw=1−20/(25*2)=.6; NF=100/111.
        expected=1+1440/1408+.0224
        self.assertAlmostEqual(v['KHbeta0'],expected)
        self.assertAlmostEqual(v['KHw'],.6)
        self.assertAlmostEqual(v['KHbeta'],1+(expected-1)*.6)
        self.assertAlmostEqual(v['KFbeta'],expected**(100/111))

    def test_formula_profile_has_numeric_trace(self):
        r=calculate({**DEFAULTS,'faceMode':'formula'})
        self.assertTrue(r['rating']['available'])
        self.assertGreater(r['rating']['faceAuto']['KHbeta0'],1)
        self.assertTrue(any(x['title']=='KHw' for x in r['trace']))

    def test_invalid_settings_are_rejected(self):
        for key,value in [('loadRegime','VI'),('loadDirection','random'),('driverClass',1.5),('accuracy',7.5),('faceMode','guess')]:
            self.assertTrue(calculate({**DEFAULTS,key:value})['errors'])

if __name__=='__main__': unittest.main()
