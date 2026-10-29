"""Механические номинальные данные двигателя; КПД не вычитается второй раз."""
import json
import math
from pathlib import Path

CATALOG = json.loads(Path(__file__).with_name('motors.json').read_text(encoding='utf-8'))


def resolve_motor(selection):
    if selection is None: return None
    if not isinstance(selection,dict): raise ValueError('Двигатель: требуется объект JSON')
    if selection.get('id') == 'custom':
        motor = selection.copy()
        for key in ('name','source'):
            if not isinstance(motor.get(key),str) or not 1 <= len(motor[key]) <= 500:
                raise ValueError('Для своего двигателя нужны название и источник паспортных данных')
        motor['manufacturer']='Пользовательские данные'
    else:
        motor = next((m.copy() for m in CATALOG if m['id']==selection.get('id')),None)
        if not motor: raise ValueError('Двигатель отсутствует в каталоге')
    for key,lo,hi in [('power',0,10000),('speed',0,100000),('efficiency',0,1),('startup',0,20),('frame',0,2000)]:
        value=motor.get(key)
        if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or not lo < value <= hi:
            raise ValueError(f'Двигатель: {key} вне диапазона ({lo}; {hi}]')
    motor['nominalTorque']=9550*motor['power']/motor['speed']
    motor['startingTorque']=motor['startup']*motor['nominalTorque']
    motor['nominalElectricalPower']=motor['power']/motor['efficiency']
    return motor
