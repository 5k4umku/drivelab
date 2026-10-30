import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from motor import resolve_motor
from assembly import calculate_assembly, from_single

class MotorTests(unittest.TestCase):
    def test_catalog_nominal_torque(self):
        m=resolve_motor({'id':'air90l4'})
        self.assertAlmostEqual(m['nominalTorque'],14.900709219858156)
        self.assertAlmostEqual(m['startingTorque'],34.27163120567376)
        self.assertAlmostEqual(m['nominalElectricalPower'],2.75)

    def test_efficiency_not_applied_twice(self):
        p=from_single();p['motor']={'id':'air90l4'}
        a=calculate_assembly(p)
        self.assertFalse(a['errors'])
        self.assertAlmostEqual(a['outputPower'],2.2*.98)
        self.assertEqual(a['stages'][0]['result']['input']['startup'],2.3)

    def test_partial_load_uses_nominal_starting_torque(self):
        p=from_single();p.update(power=1.1,motor={'id':'air90l4'})
        a=calculate_assembly(p)
        self.assertFalse(a['errors'])
        self.assertAlmostEqual(a['stages'][0]['result']['input']['startup'],4.6)

    def test_catalog_overrides_forged_nominal_values(self):
        m=resolve_motor({'id':'air90l4','power':900})
        self.assertEqual(m['power'],2.2)

    def test_insufficient_power_and_speed_mismatch_are_reported(self):
        p=from_single();p['motor']={'id':'air80b4'}
        a=calculate_assembly(p)
        failures=[c['title'] for c in a['checks'] if c['status']=='fail']
        self.assertIn('Мощность выбранного двигателя',failures)
        self.assertIn('Частота при прямом соединении двигателя',failures)

    def test_invalid_motor_and_housing(self):
        for motor in [{'id':'unknown'},{'id':'custom','power':float('nan')},'air90l4']:
            p=from_single();p['motor']=motor
            self.assertTrue(calculate_assembly(p)['errors'])
        p=from_single();p['housing']={'mode':'transparent','clearance':0}
        self.assertTrue(calculate_assembly(p)['errors'])

    def test_custom_data(self):
        m=resolve_motor(dict(id='custom',name='Двигатель 3 кВт',source='Паспорт',power=3,speed=1450,efficiency=.85,startup=2,frame=100))
        self.assertAlmostEqual(m['nominalTorque'],9550*3/1450)

if __name__=='__main__':unittest.main()
