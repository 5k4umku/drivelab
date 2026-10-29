import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from engine import DEFAULTS,calculate
for name,patch in [('helical-seminar',{}),('helical-aw250',{'aOverride':250}),('spur',{'gearType':'spur'}),('herringbone',{'gearType':'herringbone'})]:
    p={**DEFAULTS,**patch}
    (ROOT/'examples'/f'{name}.json').write_text(json.dumps({'format':'DriveLab','version':1,'engine':'0.1.0','input':p},ensure_ascii=False,indent=2),encoding='utf-8')
    r=calculate(p,compare=True)
    (ROOT/'examples'/f'{name}.result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
print('Four reproducible examples saved.')
