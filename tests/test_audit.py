"""Границы, найденные при повторной сверке ГОСТ 21354–87, 31.10.2026."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from engine import DEFAULTS, TABLES, calculate, rating_inputs
from coefficients import prepare
from rating import contact_life, bending_life


class AuditTests(unittest.TestCase):
    def test_table_material_cannot_be_forged_by_import(self):
        r=calculate({**DEFAULTS,'row1':8,'sigmaH1':99999,'row2':0})
        self.assertEqual(r['input']['sigmaH1'],670)
        self.assertEqual(r['input']['row2'],6)
        self.assertEqual(r['input']['rowName2'],'У640')

    def test_custom_properties_stay_explicit(self):
        r=calculate({**DEFAULTS,'materialMode':'custom','sigmaH1':710})
        self.assertEqual(r['input']['sigmaH1'],710)

    def test_t7_velocity_boundary_is_enforced(self):
        c={'m':2,'d1':50,'d2':200,'v':TABLES['T7']['grades']['7']['vmaxHelical']}
        self.assertFalse(rating_inputs(DEFAULTS,c).get('_tableMissing',False))
        c['v']+=.0001
        self.assertTrue(rating_inputs(DEFAULTS,c)['_tableMissing'])
        self.assertNotIn('_tableMissing',rating_inputs({**DEFAULTS,'autoTables':False},c))

    def test_grade_does_not_imply_root_polishing(self):
        for grade in (6,7,8,9):
            p,_=prepare({**DEFAULTS,'autoSurface':True,'accuracy':grade})
            self.assertEqual(p['YR'],1)
            p,_=prepare({**p,'rootFinish':'polished'})
            self.assertEqual(p['YR'],1.2)

    def test_life_values_from_hand_calculation(self):
        # Табл.11.3: 64-кратное уменьшение циклов до перегиба даёт ZN=2.
        self.assertEqual(contact_life(64e6,1e6),2)
        self.assertAlmostEqual(contact_life(1e6,2**20*1e6),.75)
        self.assertEqual(bending_life(4e6/64),2)

if __name__=='__main__': unittest.main()
