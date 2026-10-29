import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from engine import DEFAULTS,calculate
from assembly import from_single, new_shaft, calculate_assembly
for name,patch in [('helical-seminar',{}),('helical-aw250',{'aOverride':250}),('spur',{'gearType':'spur'}),('herringbone',{'gearType':'herringbone'}),('automatic-coefficients',{'loadRegime':'IV','loadDirection':'reversing','autoKA':True,'faceMode':'formula','autoSurface':True,'accuracy':8})]:
    p={**DEFAULTS,**patch}
    (ROOT/'examples'/f'{name}.json').write_text(json.dumps({'format':'DriveLab','version':1,'engine':'0.1.0','input':p},ensure_ascii=False,indent=2),encoding='utf-8')
    r=calculate(p,compare=True)
    (ROOT/'examples'/f'{name}.result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
project=from_single()
project['name']='Трёхступенчатый редуктор'
project['stages']=[dict(input={**DEFAULTS,'ratio':3,'gearType':kind,'modules':'1 1.25 1.5 2 2.5 3 4 5 6 8 10','factorsConfirmed':False},angle=angle,axial=None,hand=hand) for kind,angle,hand in [('helical',0,'right'),('spur',30,'right'),('herringbone',-30,'left')]]
project['shafts']=[new_shaft() for _ in range(4)]
out=ROOT/'examples'/'reducer-three-stage.json'
out.write_text(json.dumps(dict(format='DriveLab',version=2,engine='0.2.0',project=project),ensure_ascii=False,indent=2),encoding='utf-8')
r=calculate_assembly(project)
(ROOT/'examples'/'reducer-three-stage.result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
print('Сохранены четыре примера ступеней и один пример редуктора.')
