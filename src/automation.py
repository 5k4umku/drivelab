"""Объяснимый подбор и чувствительность. Все инженерные числа вычисляет Python."""
import copy
import json
import math
from engine import DEFAULTS, calculate, rating_inputs, r10
from rating import normative_rating
from coefficients import prepare
from assembly import calculate_assembly
from selection import zubil
from tolerances import fit


def margin(rating):
    return min(rating['margins'].values()) if rating and rating.get('available') else None


def inspect(result,load_percent=10):
    if not isinstance(load_percent,(int,float)) or isinstance(load_percent,bool) or not math.isfinite(load_percent) or not 0<=load_percent<=50:
        raise ValueError('Интервал нагрузки: 0…50 %.')
    c,p=result.get('chosen'),result.get('input')
    if not c or not p: raise ValueError('Сначала получите геометрию ступени.')
    rt=result.get('rating') or {}
    tips=[]
    def tip(title,detail,source,status='note'):
        tips.append(dict(title=title,detail=detail,source=source,status=status))
    if not rt.get('available'):
        tip('Прочность не подтверждена',rt.get('reason','Вне реализованного профиля.'),'ГОСТ 21354–87: область применения','pending')
    else:
        weak=min(rt['margins'],key=rt['margins'].get)
        tip('Определяющая проверка: '+weak,
            f"Минимальное отношение допускаемого напряжения к расчётному: {rt['margins'][weak]:.3f}. "+
            ('Увеличьте размер или рабочую ширину и сравните варианты.' if rt['margins'][weak]<1 else 'Численный запас есть; проверьте неподтверждённые условия изготовления.'),
            'ГОСТ 21354–87, формулы 31–39, пп.3.2/4.2','fail' if rt['margins'][weak]<1 else 'pass')
    if c['errorPct']>p['ratioTolerance']:
        tip('Отношение вне допуска',f"Отклонение {c['errorPct']:.4f} %, задано {p['ratioTolerance']} %. Сравните другие суммы зубьев.",'Допуск проекта; Zubil','fail')
    if p['faceMode']=='manual':
        tip('Уточните расположение опор','KHβ/KFβ заданы вручную. Режим Т5 учитывает фактическое положение венцов в конструкторе.','Т5 семинара; ГОСТ, табл.6.7/13.4','pending')
    if p['meshType']=='external' and math.gcd(c['z1'],c['z2'])>1:
        tip('Повторяемость контакта',f"НОД={math.gcd(c['z1'],c['z2'])}; одна и та же пара зубьев повторяется через {c['z2']//math.gcd(c['z1'],c['z2'])} оборотов шестерни. Это не запрет ГОСТ.",'Zubil: НОК(z₁,z₂)/z₁')
    tip('Точность и квалитет — разные параметры','Степени 6–9 изменяют fpb и динамику зубьев. IT5–IT12 задают допуск линейного размера; они не заменяют степень точности венца.','Т7 семинара; ГОСТ 25346–2013, табл.1')
    grades=[]
    scenarios=[]
    if rt.get('available'):
        for grade in (6,7,8,9):
            gp,_=prepare({**p,'accuracy':grade,'autoTables':True})
            gr=normative_rating(rating_inputs(gp,c),c,result['b'],result['T'])
            grades.append(dict(grade=grade,margin=margin(gr),h=gr.get('h'),f=max(gr['fs']) if gr.get('fs') else None,reason=gr.get('reason'),available=gr.get('available',False)))
        for label,factor in [('Нижняя нагрузка',1-load_percent/100),('Номинальная',1),('Верхняя нагрузка',1+load_percent/100)]:
            # Геометрия, частота и максимальная нагрузка фиксированы.
            # KAS обратно пропорционален T: абсолютный пусковой момент не меняется.
            sp={**p,'startup':max(1,p['startup']/factor)}
            sr=normative_rating(rating_inputs(sp,c),c,result['b'],result['T']*factor)
            scenarios.append(dict(label=label,factor=factor,torque=result['T']*factor,margin=margin(sr),h=sr.get('h'),f=max(sr['fs']) if sr.get('fs') else None,reason=sr.get('reason')))
    return dict(tips=tips,grades=grades,scenarios=scenarios,loadPercent=load_percent,
        note='Чувствительность: три расчёта одной геометрии при изменении рабочего момента. Это сценарный интервал, а не статистическая погрешность или вероятность отказа. Пусковой момент сохраняется, но не ниже рабочего.')


def search(project,index=0):
    if not isinstance(index,int) or isinstance(index,bool) or not 0<=index<len(project.get('stages',[])):
        raise ValueError('Выберите существующую ступень.')
    if len(project['stages'])>8: raise ValueError('Автоподбор ограничен восемью ступенями; ручной конструктор поддерживает 64.')
    base=calculate_assembly(project,active_index=-1)
    if base['errors']: raise ValueError('; '.join(base['errors']))
    r=base['stages'][index]['result']; p=r['input']
    if p['meshType']=='internal': raise ValueError('Для внутреннего зацепления автоподбор по прочности ещё не реализован.')
    centers=[r10(r['a']*.999999)]
    for _ in range(2): centers.append(r10(centers[-1]*1.001))
    widths=sorted({p['psiBd'],min(1.2,p['psiBd']+.2)})
    rows=[]
    for center in centers:
        for width in widths:
            for grade in (6,7,8,9):
                patch=dict(aOverride=center,psiBd=width,accuracy=grade,selectedModule=0,selectionPolicy='zubil',excludeEdges=False)
                trial=copy.deepcopy(project)
                trial['stages'][index]['input'].update(patch)
                # Проверяем весь редуктор, включая пересчёт Т5 и каскад частот.
                a=calculate_assembly(trial,active_index=-1)
                if a['errors']:
                    rows.append(dict(patch=patch,eligible=False,reason='; '.join(a['errors']),a=center,b=None,margin=None));continue
                sr=a['stages'][index]['result']; c=sr['chosen'];rt=sr['rating'] or {}
                failed=[x['title'] for x in sr['checks'] if x['status']=='fail']
                assembly_failed=[x['title'] for x in a['checks'] if x['status']=='fail']
                score=margin(rt)
                eligible=score is not None and score>=1 and not failed and not assembly_failed
                pending=sum(x['status']=='pending' for x in sr['checks'])
                rows.append(dict(patch=patch,eligible=eligible,a=c['a'],b=sr['b'],m=c['m'],z1=c['z1'],z2=c['z2'],errorPct=c['errorPct'],
                    margin=score,pending=pending,reason='; '.join(failed+assembly_failed) or rt.get('reason',''),
                    volume=(c['da1']**2+c['da2']**2)*sr['b'],outputSpeed=a['outputSpeed']))
    rows.sort(key=lambda x:(not x['eligible'],x.get('volume',math.inf) if x['eligible'] else -(x['margin'] or 0),x['patch']['accuracy']))
    return dict(rows=rows,count=len(rows),accepted=sum(x['eligible'] for x in rows),
        note='Ограниченный перебор: 3 размера R10 × до 2 ширин × 4 степени точности. Среди численно допустимых — минимальный объём венцов. Это условная рекомендация при заданных материалах и допущениях; не доказательство глобального оптимума. Каждая проба пересчитывает редуктор и опоры.')


def tools_json(payload):
    data=json.loads(payload); action=data.get('action')
    if action=='zubil': out=zubil(**data['args'])
    elif action=='fit': out=fit(**data['args'])
    elif action=='inspect':
        a=calculate_assembly(data['project'],active_index=-1)
        if a['errors']: raise ValueError('; '.join(a['errors']))
        out=inspect(a['stages'][data['index']]['result'],data.get('loadPercent',10))
    elif action=='search': out=search(data['project'],data.get('index',0))
    else: raise ValueError('Неизвестная операция подбора.')
    return json.dumps(out,ensure_ascii=False,allow_nan=False)
