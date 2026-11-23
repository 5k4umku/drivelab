"""Ступенчатая циклограмма при постоянной частоте. Приложение 3, п. 2.

Моменты на входном валу задаются долями рабочего момента, время — долями
полного ресурса. Знак момента выбирает рабочую сторону при той же скорости.
"""
import math

from rating import bending_life, normative_rating
from gost_load import face_distribution


def moments(rows, torque, hours, rpm, ratio, exponents):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise ValueError('Циклограмма должна содержать от 1 до 100 ступеней.')
    sides = {1: [], -1: []}
    fractions = []
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict) or set(row) != {'torqueRatio', 'timeFraction'}:
            raise ValueError(f'Ступень {i} должна содержать torqueRatio и timeFraction.')
        t, f = row['torqueRatio'], row['timeFraction']
        if any(isinstance(x, bool) or not isinstance(x, (float, int)) or not math.isfinite(x) for x in (t, f)):
            raise ValueError(f'Проверьте числа на ступени {i}.')
        if not 0 < f <= 1 or abs(t) > 100:
            raise ValueError(f'Ступень {i}: доля времени (0; 1], модуль отношения моментов ≤ 100.')
        fractions.append(f)
        if t:
            sides[1 if t > 0 else -1].append((abs(t) * torque, f))
    if not math.isclose(math.fsum(fractions), 1, abs_tol=1e-8, rel_tol=0):
        raise ValueError('Сумма долей времени циклограммы должна равняться единице.')
    if not any(sides.values()):
        raise ValueError('Для расчёта укажите хотя бы одну нагруженную ступень.')
    result = []
    for sign, levels in sides.items():
        if not levels:
            continue
        fraction = math.fsum(f for _, f in levels)
        def mean(q):
            return math.fsum(t ** q * f / fraction for t, f in levels) ** (1 / q)
        n = 60 * rpm * hours * fraction
        result.append(dict(sign=sign, hours=hours*fraction, cycles=[n, n/ratio],
                           TH=mean(3), TF=[mean(q) for q in exponents],
                           maxTorque=max(t for t, _ in levels)))
    return result



def _case(p, c, b, torque, step=None, check=None):
    cfg=p.get('gost',{})
    # prepare() уже перенёс пуск по табл. 24 в startup до расчёта размеров.
    cleaned={k:v for k,v in cfg.items() if k not in ('peakLoad','face27')}
    if 'face27' not in cfg:
        return normative_rating({**p,'gost':cleaned},c,b,torque,step,check)
    try:
        if p.get('faceMode','manual')!='manual' or any(k in cfg for k in ('KHbeta','KFbeta','KHbeta0')):
            raise ValueError('Табл. 27 является отдельным способом расчёта. Выберите ручной источник по ширине и удалите переопределения KHβ/KFβ.')
        if p['gearType']=='herringbone' and cfg.get('halfLoadShare',.5)!=.5:
            raise ValueError('Для неравномерно нагруженных полушевронов табл. 27 требует отдельных данных опор и сил.')
        ft=2000*torque/c['d1']
        work=face_distribution(cfg['face27'],c,b,ft,p['gearType'],p['accuracy'])
        peak=face_distribution(cfg['face27'],c,b,ft*p['startup'],p['gearType'],p['accuracy'])
    except (ValueError,TypeError,KeyError,ArithmeticError) as err:
        message=str(err)
        if check: check('Распределение нагрузки по табл. 27','pending',message)
        return dict(available=False,complete=False,reason=message,trace=[],checks=[dict(title='Табл. 27',status='pending',detail=message)])
    params=dict(KHbeta=work['KHbeta'],KFbeta=work['KFbeta'],peakKHbeta=peak['KHbeta'])
    r=normative_rating({**p,'gost':cleaned,'_face27':params},c,b,torque,step,check)
    for key in ('T','O'):
        end=work[key]
        sub='; '.join(f'{name}={end[name]:.7g}' for name in ('KT','Kf','Ks','Kb','Kfc','Kbc','KQ'))
        entry=dict(title=f'KHβ торца {key}', formula='KHβ=1+(KT+Kf+Ks+Kb+Kfc+Kbc+KQ)Kw',
                   substitution=f"{sub}; Kw={work['KW']:.7g}", value=end['KHbeta'], unit='',source='Приложение 6, табл. 27, черт. 16–24')
        r['trace'].append(entry)
        if step: step('7. Распределение по ширине венца',entry['title'],entry['formula'],entry['substitution'],entry['value'],'',entry['source'])
    r['face27']=work
    return r


def stage_rating(p, c, b, torque, step=None, check=None):
    cfg = p.get('gost', {})
    if 'spectrum' not in cfg:
        return _case(p, c, b, torque, step, check)
    trace, checks = [], []
    def record(title, status, detail):
        checks.append(dict(title=title, status=status, detail=detail))
        if check:
            check(title, status, detail)
    def emit(title, formula, sub, value, unit, source):
        trace.append(dict(title=title, formula=formula, substitution=sub, value=value, unit=unit, source=source))
        if step:
            step('7. Проверка по циклограмме момента', title, formula, sub, value, unit, source)
    def reject(message):
        record('Расчёт по циклограмме', 'pending', message)
        return dict(available=False, complete=False, checks=checks, trace=trace, reason=message)
    # Передаём ядру рабочий момент каждого отдельного случая; спектр потреблён здесь.
    base = {**p, 'gost': {k:v for k,v in cfg.items() if k != 'spectrum'},
            'muF':1., 'muH':1., 'loadDirection':'manual'}
    try:
        if cfg.get('materials') is not None:
            from gost_materials import material_properties
            passports = [material_properties(x, c['m']) for x in cfg['materials']]
            props = [(x['qF'], x['gammaA']) for x in passports]
            base['gost']['materials'] = [{**m, 'muF':1.} for m in cfg['materials']]
            if len(props) != 2:
                raise ValueError('Нужны два паспорта материалов.')
        else:
            props = [(6, .35)] * 2
        qs, gammas = zip(*props)
        if any(q not in (6, 9) for q in qs):
            raise ValueError('Для циклограммы укажите подтверждённый показатель qF каждого материала.')
        flanks = moments(cfg['spectrum'], torque, p['life'], p['speed'], c['u'], qs)
        if len(flanks) > 1 and None in gammas:
            raise ValueError('Для двусторонней нагрузки не определён γA материала.')
    except (ValueError, KeyError, TypeError, OverflowError) as error:
        return reject(str(error))
    # При пуске либо на короткой ступени абсолютный максимум сохраняется во всех проверках.
    peak = max(torque * p['startup'], *(s['maxTorque'] for s in flanks))
    for side in flanks:
        side['YN'] = [bending_life(n, q) for n,q in zip(side['cycles'], qs)]
    yas = []
    for i, gamma in enumerate(gammas):
        reduced = [s['TF'][i] / s['YN'][i] for s in flanks]
        yas.append(1. if len(reduced) == 1 else 1 - gamma * min(reduced) / max(reduced))
    source = 'ГОСТ 21354–87, приложение 3, п. 2.1–2.2, с. 65 (приближённый контакт)'
    for i, row in enumerate(cfg['spectrum'], 1):
        emit(f'Ступень циклограммы {i}', 'Ti = Tном · ti', f"ti={row['torqueRatio']}; доля времени={row['timeFraction']}", torque*row['torqueRatio'], 'Н·м', source)
    for i, ya in enumerate(yas, 1):
        emit(f'YA{i} при реверсе', 'YA=1−γA min(TFE/YN; T′FE/Y′N)/max(…); при одной стороне YA=1',
             ' / '.join(f"{s['TF'][i-1]:.7g} Н·м при YN={s['YN'][i-1]:.7g}" for s in flanks), ya, '', 'Табл. 13, п. 10.6–10.6.3')
    cases = []
    for side in flanks:
        label = 'прямой ход' if side['sign'] > 0 else 'обратный ход'
        for mode, t, ya in [('H', side['TH'], yas[0]), ('F1', side['TF'][0], yas[0]), ('F2', side['TF'][1], yas[1])]:
            q = 3 if mode == 'H' else qs[int(mode[1])-1]
            emit(f'Эквивалентный момент {mode}, {label}', 'TE = (Σ |Ti|^q Ni / Σ Ni)^(1/q)',
                 f"q={q}; N₁={side['cycles'][0]:.9g}; N₂={side['cycles'][1]:.9g}", t,'Н·м',source)
            rp = {**base,'life':side['hours'],'YA':ya,'startup':peak/t}
            if mode == 'H' and cfg.get('subsurface') and cfg.get('materials'):
                subsurface=cfg['subsurface']
                if isinstance(subsurface,list) and len(subsurface)==2:
                    rp['gost']={**rp['gost'],'subsurface':[{**s,'cycles':side['cycles'][i]} if isinstance(s,dict) and str(cfg['materials'][i].get('row')) in ('16.5','16.6') else s for i,s in enumerate(subsurface)]}
            r = _case(rp, c, b, t)
            if not r.get('available'):
                return reject(f"{label}, {mode}: {r.get('reason','исходные данные вне области метода')}")
            cases.append((mode, label, r))
    # H и F имеют разные эквивалентные моменты. Сравниваем только соответствующие
    # компоненты, затем возвращаем определяющую сторону для каждого критерия.
    depth_keys = tuple(k for k in cases[0][2]['margins'] if k.startswith('Hdepth'))
    groups = {'H':('H','Hmax',*depth_keys), 'F1':('F1','Fmax1'), 'F2':('F2','Fmax2')}
    governing = {key: min(((label,r) for m,label,r in cases if m==mode), key=lambda item:-math.inf if item[1]['margins'][key] is None else item[1]['margins'][key])
                 for mode, keys in groups.items() for key in keys}
    margins = {key:r['margins'][key] for key,(_,r) in governing.items()}
    out = dict(governing['H'][1])
    fr = [governing[f'F{i}'][1] for i in (1,2)]
    fmax = [governing[f'Fmax{i}'][1] for i in (1,2)]
    out.update(fs=[r['fs'][i] for i,r in enumerate(fr)], fAllow=[r['fAllow'][i] for i,r in enumerate(fr)],
               hmax=governing['Hmax'][1]['hmax'], hMaxAllow=governing['Hmax'][1]['hMaxAllow'],
               fsmax=[r['fsmax'][i] for i,r in enumerate(fmax)], fMaxAllow=[r['fMaxAllow'][i] for i,r in enumerate(fmax)],
               YN=[r['YN'][i] for i,r in enumerate(fr)], marginH=margins['H'], marginF=[margins['F1'],margins['F2']], margins=margins)
    out.update(sigmaF=out['fs'], fp=out['fAllow'], sigmaFmax=out['fsmax'], fpmax=out['fMaxAllow'],
               sigmaHmax=out['hmax'], hpmax=governing['Hmax'][1]['hpmax'])
    # Разные ветви могут назначить разные коэффициенты. В отчёте каждая
    # подстановка сопровождается стороной и компонентом, к которым относится.
    labels = {'H':'контакт', 'F1':'изгиб шестерни', 'F2':'изгиб колеса'}
    stress_titles = {'Контактная выносливость','Изгибная выносливость шестерни','Изгибная выносливость колеса',
                     'Контакт при максимуме','Изгиб шестерни при максимуме','Изгиб колеса при максимуме'}
    seen = set()
    for mode, label, r in cases:
        for x in r['checks']:
            if x['title'] not in stress_titles and (x['title'],x['status'],x['detail']) not in seen:
                record(x['title'],x['status'],x['detail'])
                seen.add((x['title'],x['status'],x['detail']))
        for x in r['trace']:
            emit(f"{label}, {labels[mode]} · {x['title']}", x['formula'], x['substitution'], x['value'], x['unit'], x['source'])
    for key,(label,r) in governing.items():
        if margins[key] is None:
            record(f'Запас {key} по циклограмме', 'pending', f'{label}, допускаемое напряжение не установлено для данного материала.')
            continue
        record(f'Запас {key} по циклограмме', 'pass' if margins[key] >= 1 else 'fail',
               f'{label}, отношение допускаемого напряжения к расчётному {margins[key]:.6g} при требовании ≥ 1.')
    out.update(mandatoryPending=any(r.get('mandatoryPending') for _,_,r in cases), complete=all(ch['status']=='pass' for ch in checks), checks=checks, trace=trace,
               spectrum=dict(flanks=flanks,YA=yas,peak=peak,governing={key:name for key,(name,_) in governing.items()}))
    return out
