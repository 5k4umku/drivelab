"""Предварительные размеры внешней передачи по разделу 5 приложения 1 ГОСТ 21354–87."""
import math
from bisect import bisect_left

from coefficients import REGIMES
from gost_geometry import tooth_form_factor
from gost_spectrum import conditions_issue
from gost_materials import material_properties
from rating import bending_life, contact_life


# Черт. 13а и 13б, с. 58–59. Узлы сняты с графиков до сотых.
# Обычные ординаты даны с шагом 0,2 по ψbd; последняя точка — конец кривой.
# Каждая строка: (регулярные значения, абсцисса конца, ордината конца).
CURVES = {
    ('H', False): (
        ((1.07,1.18,1.30),.73,1.40), ((1.05,1.12,1.20,1.28),.85,1.30),
        ((1.02,1.05,1.08,1.12,1.16,1.20,1.24),1.62,1.30),
        ((1.01,1.03,1.06,1.08,1.10,1.13,1.16,1.20,1.24),2.,1.30),
        ((1.01,1.02,1.04,1.06,1.08,1.10,1.13,1.16,1.20),2.,1.25),
        ((1.01,1.02,1.03,1.04,1.05,1.07,1.09,1.12,1.15),2.,1.19),
        ((1.,1.01,1.02,1.02,1.03,1.04,1.06,1.08,1.10),2.,1.12)),
    ('H', True): (
        ((1.21,1.44),.45,1.50), ((1.10,1.24,1.44),.65,1.50),
        ((1.06,1.12,1.20,1.29,1.38,1.48),1.24,1.50),
        ((1.04,1.09,1.15,1.20,1.28,1.36),1.30,1.40),
        ((1.02,1.05,1.09,1.14,1.20,1.26),1.42,1.32),
        ((1.01,1.03,1.05,1.08,1.12,1.17,1.22),1.59,1.27),
        ((1.,1.01,1.03,1.04,1.07,1.10,1.13),1.59,1.16)),
    ('F', False): (
        ((1.17,1.38,1.66),.73,1.86), ((1.10,1.23,1.39,1.58),.88,1.67),
        ((1.05,1.11,1.18,1.26,1.34,1.43,1.52,1.62),1.80,1.72),
        ((1.03,1.07,1.12,1.18,1.24,1.30,1.38,1.46,1.55),2.,1.63),
        ((1.02,1.05,1.09,1.13,1.17,1.23,1.29,1.37,1.45),2.,1.56),
        ((1.01,1.03,1.05,1.08,1.11,1.15,1.20,1.26,1.33),2.,1.41),
        ((1.,1.01,1.02,1.04,1.06,1.09,1.13,1.17,1.21),2.,1.27)),
    ('F', True): (
        ((1.34,1.73),.48,1.90), ((1.20,1.44,1.70),.71,1.90),
        ((1.09,1.18,1.30,1.43,1.57,1.71),1.23,1.74),
        ((1.04,1.11,1.18,1.28,1.39,1.51),1.38,1.67),
        ((1.02,1.07,1.13,1.20,1.29,1.40),1.39,1.51),
        ((1.01,1.04,1.08,1.14,1.21,1.30),1.44,1.42),
        ((1.,1.01,1.03,1.06,1.10,1.15,1.21),1.60,1.30)),
}


def _positive(x, name):
    if type(x) not in (int, float) or not math.isfinite(x) or x <= 0:
        raise ValueError(f'{name}: требуется положительное конечное число')
    return x


def chart_factor(criterion, hard_pair, scheme, psi_bd):
    """Интерполяция по соответствующей кривой черт. 13а или 13б."""
    if criterion not in ('H','F') or type(hard_pair) is not bool or type(scheme) is not int or not 1 <= scheme <= 7:
        raise ValueError('Для черт. 13а/б нужны критерий H/F, группа твёрдости по HV и номер схемы 1–7')
    _positive(psi_bd, 'ψbd')
    regular, limit, end = CURVES[criterion, hard_pair][scheme - 1]
    if psi_bd > limit:
        raise ValueError(f'Для схемы {scheme} график K{criterion}β заканчивается при ψbd≈{limit:g}')
    xs = [i / 5 for i in range(len(regular) + 1)] + [limit]
    ys = [1, *regular, end]
    j = bisect_left(xs, psi_bd)
    return ys[j-1] + (ys[j] - ys[j-1]) * (psi_bd - xs[j-1]) / (xs[j] - xs[j-1])


def _dimensions(kind, z1, u, eb, b, aw, psi, kh, kf, th, tf, hp, fp, yfs):
    spur = kind == 'spur'
    high_overlap = kind == 'herringbone' or eb > 1
    kd, k_a = (770., 495.) if spur else (675., 430.)
    km, kma = (14.,1400.) if spur else (11.2,850.) if high_overlap else (12.5,1100.)
    psi_ba = 2 * psi / (u + 1)
    dw = kd * (th * kh * (u+1) / (psi * hp**2 * u**2)) ** (1/3)
    center = k_a * (u+1) * (th * kh / (u**2 * psi_ba * hp**2)) ** (1/3)
    m_width = km * (tf * kf * yfs / (u * z1**2 * psi * fp)) ** (1/3)
    # Во второй формуле п. 5.2.3 коэффициент Kмa уже учитывает способ оценки.
    m_center = kma * tf * (u+1) * yfs / (u * aw * b * fp)
    return dict(dw1=dw, aW=center, moduleByWidth=m_width, moduleByCenter=m_center,
                Kd=kd, Ka=k_a, Km=km, Kma=kma)


def project_design(p, c, b, torque, rating):
    """Оценка по пп. 5.1 и 5.2 для текущего варианта и его расчётных нагрузок."""
    try:
        return _project_design(p,c,b,torque,rating)
    except (KeyError, ValueError, TypeError, ArithmeticError, IndexError) as error:
        return dict(available=False, reason=str(error), trace=[])


def _life_inputs(p, c, b, torque):
    """Долговечность для предварительного выбора без расчёта рабочих напряжений."""
    gost = p.get('gost',{})
    if 'materials' in gost:
        mats = [material_properties(m,c['m']) for m in gost['materials']]
        if len(mats) != 2:
            raise ValueError('Нужны паспорта материалов шестерни и колеса')
    else:
        if any(p.get(f'treatment{i}','У') != 'У' for i in (1,2)):
            raise ValueError('Для выбранной термообработки укажите паспорт материала колеса')
        mats = [dict(sigmaHlim=p[f'sigmaH{i}'], SH=p['SH'], sigmaFlimb0=p[f'sigmaF{i}'],
                     NHlim=p[f'NHG{i}']*1e6, homogeneous=True, qF=6, muF=None) for i in (1,2)]
    normal_cycles = 60 * _positive(p['speed'],'n₁') * _positive(p['life'],'L')
    beta = math.radians(c['beta'])
    width = b / 2 if p['gearType']=='herringbone' else b
    out = dict(materialProperties=mats,epsilonBeta=width*abs(math.sin(beta))/(math.pi*c['m']),
               YFS=[tooth_form_factor(c['z1']/math.cos(beta)**3,p.get('x1',0),gost.get('tool1','standard'))])
    if 'spectrum' in gost:
        from gost_spectrum import moments
        qs = [m['qF'] for m in mats]
        if any(q not in (6,9) for q in qs):
            raise ValueError('Для циклограммы нужны показатели усталости qF из паспортов')
        sides = moments(gost['spectrum'],torque,p['life'],p['speed'],c['u'],qs)
        for side in sides:
            side['YN'] = [bending_life(n,q) for n,q in zip(side['cycles'],qs)]
        out['spectrum'] = dict(flanks=sides)
    else:
        mu = mats[0].get('muF')
        if mu is None:
            mu = p['muF']
            q = mats[0]['qF']
            if q != p.get('mF',6) and mu != 1:
                regime = str(p.get('loadRegime'))
                if q not in (6,9) or regime not in REGIMES:
                    raise ValueError('Для проектирования задайте μF шестерни для показателя qF выбранного материала')
                mu = REGIMES[regime][2 if q==9 else 1]
        nf = normal_cycles * _positive(mu,'μF')
        if mats[0]['qF'] is None and nf < 4e6:
            raise ValueError('Для заданного ресурса требуется показатель qF шестерни')
        out['YN'] = [bending_life(nf,mats[0]['qF']) if mats[0]['qF'] else 1.]
        out['ZN'] = [contact_life(m['NHlim'],normal_cycles*p['muH']/ratio,m['homogeneous'])
                     for m,ratio in zip(mats,(1,c['u']))]
    return out


def _history_flanks(history, passports):
    """One physical operating point per loaded flank gives an unambiguous sizing load."""
    sides = history['sides'].values() if 'sides' in history else [history]
    flanks = []
    for side in sides:
        levels = side['levels']
        points = {(row['speed'], row['torque']) for row in levels}
        if len(points) != 1:
            raise ValueError('Раздел 5: для меняющегося момента или частоты на одной стороне '
                             'расчётная нагрузка по истории требует отдельного обоснования.')
        members = side['members']
        cycles = [member['contact']['cycles'] for member in members]
        nf = members[0]['bending']['cycles']
        if min(*cycles, nf) <= 0:
            raise ValueError('Раздел 5: по истории не определены циклы контактной или изгибной выносливости.')
        level = levels[0]
        yn = bending_life(nf, passports[0]['qF'])
        flanks.append(dict(sign=level['sign'], cycles=cycles, YN=[yn],
                           TH=level['torque'], TF=[level['torque']]))
    return flanks


def _project_design(p, c, b, torque, rating):
    cfg = p.get('gost',{}).get('design',{})
    allowed = {'scheme','hardPair','psiBd','psiBa','centerDistance','width','KHbeta','KFbeta','YFS1','reversing'}
    if not isinstance(cfg, dict) or set(cfg)-allowed:
        raise ValueError('Проверьте названия входов раздела 5 в gost.design')
    if p.get('meshType','external') != 'external':
        raise ValueError('Раздел 5 применяется к внешней паре')
    kind = p['gearType']
    if kind not in ('spur','helical','herringbone'):
        raise ValueError('Неизвестный тип цилиндрической передачи')
    if kind == 'herringbone' and p.get('gost',{}).get('halfLoadShare',.5) != .5:
        raise ValueError('Проектировочные коэффициенты шеврона относятся к паре с равной нагрузкой полушевронов')
    if c.get('m',1)<1 or c.get('v',0)>25 or not p.get('gost',{}).get('oil',True) or p.get('alpha',20)!=20:
        raise ValueError('Геометрия или режим работы выходит за область ГОСТ 21354–87')
    gost = p.get('gost', {})
    if 'conditions' in gost:
        issue = conditions_issue(gost['conditions'], appendix=True)
        if issue:
            raise ValueError(issue)
    historical = p.get('gost', {}).get('spectrumMethod') in ('cycles', 'stresses')
    if historical and not rating.get('history'):
        raise ValueError('Раздел 5: отсутствует подтверждённая история нагрузок. '
                         + rating.get('reason', 'Проверьте режим и исходные данные.'))
    if 'roots' in p.get('gost', {}):
        raise ValueError('Раздел 5: влияние фактической геометрии корня на YFS требует подтверждения.')
    if not rating.get('available'):
        if rating.get('reasonCode') != 'missingDynamicMeasurements':
            raise ValueError(rating.get('reason', 'Требуется уточнить исходные данные для раздела 5.'))
        rating = _life_inputs(p,c,b,torque)
    u = _positive(c['u'],'u')
    aw = _positive(cfg.get('centerDistance',c.get('aW',c.get('a'))),'aw')
    width = _positive(cfg.get('width',b),'b')
    # При сравнении двух назначенных ширин сохраняем нормальный модуль и β
    # выбранного варианта; осевое перекрытие меняется пропорционально ширине.
    eb = rating['epsilonBeta'] * width / b
    if 'psiBd' in cfg and 'psiBa' in cfg:
        raise ValueError('Задайте одно отношение ширины: ψbd или ψba')
    psi = (_positive(cfg['psiBa'],'ψba') * (u+1)/2 if 'psiBa' in cfg
           else _positive(cfg.get('psiBd',p.get('psiBd',b*(u+1)/(2*aw))),'ψbd'))
    passports = rating.get('materialProperties') or [
        dict(sigmaHlim=p[f'sigmaH{i}'], SH=p['SH'], sigmaFlimb0=p[f'sigmaF{i}'],
             NHlim=p[f'NHG{i}']*1e6, homogeneous=True, qF=6) for i in (1,2)]
    if 'scheme' in cfg:
        if 'KHbeta' in cfg or 'KFbeta' in cfg:
            raise ValueError('Выберите схему черт. 13а/б или задайте оба коэффициента вручную')
        if all('hv' in mat for mat in passports):
            hard = min(mat['hv'] for mat in passports) > 350
            if 'hardPair' in cfg and (type(cfg['hardPair']) is not bool or hard != cfg['hardPair']):
                raise ValueError('Выбранная ветвь 350 HV противоречит паспортам материалов')
        elif 'hardPair' in cfg:
            hard = cfg['hardPair']
        else:
            hard = _positive(p.get('faceHV'),'HV менее твёрдого венца') > 350
        kh, kf = [chart_factor(label,hard,cfg['scheme'],psi) for label in ('H','F')]
        origin = f"Черт. 13а/б, схема {cfg['scheme']}, " + ('оба венца >350 HV' if hard else 'хотя бы один венец ≤350 HV')
    else:
        if 'hardPair' in cfg:
            raise ValueError('Ветвь твёрдости применяется при выбранной схеме черт. 13а/б')
        kh = _positive(cfg.get('KHbeta',p['KHbeta']),'KHβ')
        kf = _positive(cfg.get('KFbeta',p['KFbeta']),'KFβ')
        if min(kh,kf) < 1:
            raise ValueError('Коэффициенты KHβ и KFβ должны быть не меньше 1')
        origin = 'Коэффициенты распределения по ширине заданы в проекте'
    if 'reversing' in cfg and type(cfg['reversing']) is not bool:
        raise ValueError('Признак реверсивной нагрузки должен быть логическим')
    spectrum = rating.get('spectrum',{}).get('flanks',[])
    if historical:
        spectrum = _history_flanks(rating['history'], passports)
    reverse = len(spectrum)>1 if spectrum else p.get('loadDirection')=='reversing' or (
        p.get('loadDirection','manual')=='manual' and p.get('YA',1)<1)
    if 'reversing' in cfg:
        if (spectrum or p.get('loadDirection') in ('oneway','reversing')) and reverse != cfg['reversing']:
            raise ValueError('Признак реверса противоречит направлениям нагрузки проекта')
        reverse = cfg['reversing']
    yfs = _positive(cfg.get('YFS1',rating['YFS'][0]),'YFS1')
    _positive(torque,'момент входного вала')
    cases = []
    for side in spectrum or [None]:
        if side:
            zn = [contact_life(mat['NHlim'],cycles,mat['homogeneous'])
                  for mat,cycles in zip(passports,side['cycles'])]
            yn = side['YN'][0]
            th, tf = side['TH']*u, side['TF'][0]*u
            label = 'прямой ход' if side['sign']>0 else 'обратный ход'
        else:
            zn, yn = rating['ZN'],rating['YN'][0]
            th = tf = torque*u
            label = 'рабочая нагрузка'
        hp_members = [.9*_positive(mat['sigmaHlim'],'σHlim')*z/mat['SH'] for mat,z in zip(passports,zn)]
        hp = min(hp_members) if kind=='spur' else min(.45*sum(hp_members),1.23*min(hp_members))
        fp = .4*_positive(passports[0]['sigmaFlimb0'],'σFlimb0')*yn*(.75 if reverse else 1)
        item = _dimensions(kind,c['z1'],u,eb,width,aw,psi,kh,kf,th,tf,hp,fp,yfs)
        cases.append(dict(item, side=label, T2H=th, T2F=tf, HP=hp, FP1=fp, hpMembers=hp_members, YN=yn))
    h = max(cases,key=lambda x:x['aW'])
    f = max(cases,key=lambda x:x['moduleByWidth'])
    result = dict(available=True, dw1=h['dw1'], aW=h['aW'], HP=h['HP'], FP1=f['FP1'],
                  moduleByWidth=f['moduleByWidth'], moduleByCenter=f['moduleByCenter'],
                  KHbeta=kh,KFbeta=kf,YFS1=yfs,psiBd=psi,psiBa=2*psi/(u+1),cases=cases,
                  source=origin, trace=[])
    def add(title, formula, value, unit, point, substitution):
        result['trace'].append(dict(title=title,formula=formula,value=value,unit=unit,
                                    source='ГОСТ 21354–87, прил. 1, '+point,substitution=substitution))
    for case in cases:
        for symbol in ('T2H', 'T2F'):
            add(f"{symbol}, {case['side']}", 'T₂ = T₁ u', case[symbol], 'Н·м',
                'пп. 5.1.3, 5.2.4', f"{case['side']}, u={u:.7g}, T₂={case[symbol]:.7g} Н·м")
    add('KHβ для предварительных размеров','KHβ(ψbd, схема, HV)',kh,'','п. 5.1.4',f'{origin}, ψbd={psi:.6g}')
    add('KFβ для предварительных размеров','KFβ(ψbd, схема, HV)',kf,'','п. 5.2.5',f'{origin}, ψbd={psi:.6g}')
    add('Допускаемое σHP для проектирования','σHPi=0,9 σHlimi ZNi/SHi',h['HP'],'МПа','пп. 5.1.5–5.1.6',
        f"{h['side']}, σHP₁={h['hpMembers'][0]:.6g}, σHP₂={h['hpMembers'][1]:.6g}; "
        + ('минимум' if kind=='spur' else 'min[0,45(σHP₁+σHP₂); 1,23 min σHPᵢ]'))
    add('Допускаемое σFP1 для проектирования','σFP1=0,4 σFlimb0 YN (0,75 при реверсе)',f['FP1'],'МПа','п. 5.2.6',
        f"{f['side']}, σFlimb0={passports[0]['sigmaFlimb0']:.6g} МПа, YN={f['YN']:.6g}, множитель реверса={.75 if reverse else 1}")
    add('Начальный диаметр шестерни','dw1=Kd ∛[T2H KHβ(u+1)/(ψbd σHP² u²)]',h['dw1'],'мм','п. 5.1.2',
        f"Kd={h['Kd']:g}, T2H={h['T2H']:.6g} Н·м, u={u:.6g}, ψbd={psi:.6g}")
    add('Межосевое расстояние','aw=Ka(u+1) ∛[T2H KHβ/(u² ψba σHP²)]',h['aW'],'мм','п. 5.1.2',
        f"Ka={h['Ka']:g}, ψba={result['psiBa']:.6g}, σHP={h['HP']:.6g} МПа")
    add('YFS1 шестерни','Коэффициент формы зуба шестерни',yfs,'','п. 5.2.7',
        'Значение по черт. 10 введено пользователем' if 'YFS1' in cfg else 'Приближение по табл. 13, п. 6 для выбранного инструмента')
    add('Модуль по относительной ширине','m=Km ∛[T2F KFβ YFS1/(u z₁² ψbd σFP1)]',f['moduleByWidth'],'мм','п. 5.2.3',
        f"Km={f['Km']:g}, εβ={eb:.6g}, T2F={f['T2F']:.6g} Н·м, z₁={c['z1']}, YFS1={yfs:.6g}")
    add('Модуль при заданном межосевом','m=Kma T2F(u+1)YFS1/(u aw bw σFP1)',f['moduleByCenter'],'мм','п. 5.2.3',
        f"Kma={f['Kma']:g}, aw={aw:.6g} мм, bw={width:.6g} мм, σFP1={f['FP1']:.6g} МПа")
    return result
