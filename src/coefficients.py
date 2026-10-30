"""Таблицы и формулы с явной областью применения. Размеры — мм, Н, МПа.

Т5 — учебное приближение из семинара, не таблица ГОСТ 21354–87.
Не экстраполируем таблицы и не заменяем отсутствующий ответ единицей.
"""
import math

REGIMES = {
    '0': (1., 1., 1.), 'I': (.500, .300, .200),
    'II': (.250, .143, .100), 'III': (.180, .065, .063),
    'IV': (.125, .038, .016), 'V': (.063, .013, .004),
}
# III/qF=9: в скане ГОСТ табл.35 напечатано .063, в Т2 семинара .036.
# Профиль У использует qF=6; спорную колонку не применяем к нему.
KA_TABLE = ((1., 1.25, 1.5, 1.75), (1.1, 1.35, 1.6, 1.85),
            (1.25, 1.5, 1.75, 2.), (1.5, 1.75, 2., 2.25))
T5_WIDTHS = (.4, .6, .8, 1., 1.2, 1.4, 1.6)
T5 = {
    'symmetric-no-axial': (1.01, 1.02, 1.02, 1.02, 1.03, 1.04, 1.06),
    'symmetric-axial': (1.02, 1.03, 1.03, 1.04, 1.06, 1.08, 1.11),
    'pinion-offset': (1.02, 1.04, 1.05, 1.07, 1.08, 1.12, 1.15),
    'wheel-offset': (1.03, 1.05, 1.08, 1.10, 1.13, 1.17, 1.20),
    'both-offset': (1.05, 1.08, 1.12, 1.15, 1.18, 1.23, 1.28),
    'console-roller': (1.12, 1.18, 1.27, None, None, None, None),
    'console-ball': (1.17, 1.27, 1.45, None, None, None, None),
}
T5_NAMES = {'symmetric-no-axial': 'оба симметрично, Fa=0',
            'symmetric-axial': 'оба симметрично, Fa>0',
            'pinion-offset': 'шестерня несимметрично',
            'wheel-offset': 'колесо несимметрично', 'both-offset': 'оба несимметрично',
            'console-roller': 'консольно, роликовые опоры', 'console-ball': 'консольно, шариковые опоры'}


def t5_factor(width, case):
    """Линейная интерполяция соседних строк. Прочерк — отсутствие данных."""
    if case not in T5 or not math.isfinite(width) or not .4 <= width <= 1.6:
        return None
    values = T5[case]
    for i, x in enumerate(T5_WIDTHS):
        if math.isclose(width, x, abs_tol=1e-10):
            return dict(value=values[i], lower=x, upper=x) if values[i] else None
        if width < x:
            lo, hi = values[i-1], values[i]
            if lo is None or hi is None: return None
            return dict(value=lo+(hi-lo)*(width-T5_WIDTHS[i-1])/(x-T5_WIDTHS[i-1]),
                        lower=T5_WIDTHS[i-1], upper=x)
    return None


def layout_case(z, shafts, axial_force):
    positions = []
    for s in shafts:
        a, b = s['A']['z'], s['B']['z']
        positions.append('console' if z <= a or z >= b else
                         'symmetric' if abs(z-(a+b)/2) <= 1e-6 else 'offset')
    if 'console' in positions:
        # Наиболее податливый из консольных валов определяет столбец Т5.
        ball = any(s['bearing'] == 'ball' for s, pos in zip(shafts, positions) if pos == 'console')
        return 'console-ball' if ball else 'console-roller'
    if positions == ['symmetric', 'symmetric']:
        return 'symmetric-axial' if abs(axial_force) > 1e-8 else 'symmetric-no-axial'
    return 'both-offset' if positions == ['offset', 'offset'] else 'pinion-offset' if positions[0] == 'offset' else 'wheel-offset'


def prepare(p):
    """Параметры, не зависящие от окончательной геометрии; журнал выбора."""
    p = dict(p)
    if p.get('faceMode','manual') != 'manual':
        p['gost']={k:v for k,v in p.get('gost',{}).items() if k not in ('KHbeta','KFbeta','KHbeta0')}
    audit = []
    def add(key, value, formula, detail, source):
        p[key] = value
        audit.append(dict(title=key, value=value, formula=formula, substitution=detail, source=source, unit=''))
    regime = p.get('loadRegime', 'manual')
    if regime != 'manual':
        mh, mf6, mf9 = REGIMES[regime]
        mf = mf6 if p['mF'] == 6 else mf9
        add('muH', mh, 'NHE=μH NΣ', f'Режим {regime} → μH={mh}', 'ГОСТ 21354–87, табл.35; режим 0 — постоянная нагрузка')
        add('muF', mf, 'NFE=μF NΣ', f'Режим {regime}, qF={p["mF"]} → μF={mf}', 'ГОСТ 21354–87, табл.35')
    direction = p.get('loadDirection', 'manual')
    if direction != 'manual':
        # Равные моменты и числа циклов на двух сторонах: YN=YN′.
        gamma = .35 if p['treatment1'] == p['treatment2'] == 'У' else None
        if direction == 'oneway':
            add('YA', 1., 'YA=1', 'Одностороннее нагружение', 'ГОСТ 21354–87, табл.13, п.10.6')
        elif gamma is not None:
            add('YA', 1-gamma, 'YA=1−γA·min(TF/YN;TF′/YN′)/max(TF/YN;TF′/YN′)',
                'Симметричный реверс: TF=TF′, YN=YN′; 1−0,35=0,65. Ресурс задан для каждой стороны зуба.',
                'ГОСТ 21354–87, табл.13, пп.10.6–10.6.3')
    if p.get('autoKA'):
        row, col = p['driverClass'], p['machineClass']
        value = KA_TABLE[row][col]
        add('KA', value, 'KA=таблица(режим двигателя; режим машины)',
            f'Строка {row+1}, столбец {col+1}' + ('; нижняя граница «и выше», требуется обоснование' if row >= 2 and col == 3 else ''),
            'ГОСТ 21354–87, приложение4, табл.21–23; вне резонанса')
    if p.get('autoSurface'):
        grade = p['accuracy']
        polished = p.get('rootFinish','cut') == 'polished'
        add('YR', 1.2 if polished else 1., 'YR=1,2 при полировании У; иначе 1',
            'Полирование переходной поверхности' if polished else 'Зубофрезерование/шлифование, Rz≤40 мкм',
            'ГОСТ 21354–87, табл.13, п.13, с.36. Степень точности не доказывает полирование корня.')
        add('ZR', 1. if grade in (6, 7) else .95, 'ZR по Т4', f'Точность {grade}; шероховатость по Т4', 'Т4 семинара; требование к изготовлению')
    return p, audit


def face_factors(*, width, diameter, module, ea, beta, at, force, ka, khv,
                 stiffness, zeps, velocity, hv, deviation, torque_side):
    """Табл.6.7/6.7.1/6.7.2 и13.4, x=0, прямые/косые, b/d≤1,3.

    deviation=fkβ⁰ — ПОЛНОЕ отклонение контактных линий (деформации и
    погрешности изготовления); нельзя подменять одним допуском Fβ.
    """
    if width/diameter > 1.3: raise ValueError('Формула KHβ⁰ требует b/d₁≤1,3')
    kk = .14 if torque_side == 'input' else -.08
    initial = 1 + .4*width*deviation*stiffness*math.cos(at)/(force*ka*khv*zeps**2) + kk*(width/diameter)**2
    if initial < 1: raise ValueError('KHβ⁰<1: проверьте fkβ⁰ и торец концентрации нагрузки')
    running = 1-20/((.01*hv+2)**2*(velocity+4)**.25)
    if not 0 < running <= 1: raise ValueError('KHw вне области формулы')
    khb = 1+(initial-1)*running
    h = 2*module if abs(beta) > 1e-9 else 2*module/ea
    bh = width/h
    nf = bh**2/(bh**2+bh+1)
    return dict(KHbeta0=initial, KHw=running, KHbeta=khb, KFbeta=initial**nf, NF=nf, h=h, Kk=kk)
