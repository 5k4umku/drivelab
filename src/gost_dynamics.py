"""Внутренняя динамическая нагрузка. ГОСТ 21354–87, таблицы 6–9, 13, 25 и 26."""
import math


class MissingDynamicMeasurements(ValueError):
    """Operating dynamic factors need measurements that preliminary sizing does not use."""


def _value(value, name, *, zero=False):
    if (type(value) not in (float, int) or not math.isfinite(value)
            or value < 0 or (not zero and value == 0)):
        raise ValueError(f'Динамика: проверьте величину «{name}» и её единицы')
    return value


def resonance_state(g, stiffness, config, mesh_width=None):
    """Положение частоты n₁ относительно главного резонанса; g из external_geometry."""
    keys = {'resonanceRpm', 'inertia1', 'inertia2', 'pitchError', 'profileError',
            'coefficients', 'coefficientSource', 'attachedRatio'}
    if not isinstance(config, dict) or set(config) - keys:
        raise ValueError('Проверьте названия параметров в gost.dynamics')
    for key in ('resonanceRpm', 'inertia1', 'inertia2', 'pitchError', 'profileError', 'attachedRatio'):
        if key in config:
            _value(config[key], key, zero=key in ('pitchError', 'profileError', 'attachedRatio'))
    coeffs = config.get('coefficients', {})
    if not isinstance(coeffs, dict) or set(coeffs) - {'Cv2', 'Cv4', 'Cv5', 'Cv6'}:
        raise ValueError('Для εγ>2 доступны входы Cv2, Cv4, Cv5 и Cv6')
    for name, value in coeffs.items():
        _value(value, name)
    source = config.get('coefficientSource', '')
    if not isinstance(source, str) or (coeffs and not source.strip()):
        raise ValueError('Укажите источник введённых коэффициентов Cv')
    inertias = 'inertia1' in config or 'inertia2' in config
    if inertias and (not {'inertia1','inertia2'} <= config.keys() or 'resonanceRpm' in config):
        raise ValueError('Для определения nE1 задайте оба момента инерции либо частоту резонанса')
    gamma = config.get('attachedRatio', 0)
    mred = None
    if 'resonanceRpm' in config:
        freq, method = config['resonanceRpm'], 'input'
    elif inertias:
        rb1, rb2 = g['db1'] / 2, g['db2'] / 2
        inv_mass = rb1**2 / (config['inertia1'] * (1 + gamma)) + rb2**2 / config['inertia2']
        mred = 1 / inv_mass
        width = g['bWidth'] if mesh_width is None else _value(mesh_width, 'активная ширина')
        cg = _value(stiffness, 'c′') * (.75 * g['epsilonAlpha'] + .25)
        # cγ b в Н/мкм; для кг переводим жёсткость в Н/м.
        freq = 30 / (math.pi * g['z1']) * math.sqrt(1e6 * cg * width / mred)
        method = 'inertia'
    else:
        u2 = g['u'] ** 2
        numerator = 2.4e7 * math.cos(math.radians(g['alphaT']))
        root = g['epsilonAlpha'] * math.cos(math.radians(g['betaB']))
        # Множитель (u²+1+γ)/(1+γ) следует из отношения приведённых масс в п. 1.2.
        freq = numerator / (g['z1'] * g['d2']) * math.sqrt(root * (u2 + 1 + gamma) / (1 + gamma))
        method = 'estimate'
    _value(freq, 'nE1')
    ratio = g['speed'] / freq
    if ratio < .85:
        zone = 'subcritical'
    elif ratio <= 1.15:
        zone = 'resonant'
    elif ratio < 1.5:
        zone = 'transition'
    else:
        zone = 'supercritical'
    return dict(nE1=freq, ratio=ratio, zone=zone, method=method, reducedMassKg=mred)


def subcritical_forces(m, accuracy, soft, helical, tip_relief, aw, u, v, gamma=0):
    if accuracy not in range(5, 11):
        raise ValueError('Для дорезонансной зоны таблицы 7 и 9 охватывают степени точности 5–10')
    row = 0 if m <= 3.55 else 1 if m <= 10 else 2
    col = int(accuracy) - 5
    g0 = ((2.8,3.8,4.7,5.6,7.3,10.), (3.1,4.2,5.3,6.1,8.2,11.), (3.7,4.8,6.4,7.3,10.,13.5))[row][col]
    limit = ((85,160,240,380,700,1200), (105,194,310,410,880,1500), (150,250,450,590,1050,1800))[row][col]
    if helical:
        dh, df = (.02 if soft else .04), .06
    elif tip_relief:
        dh, df = (.04 if soft else .10), .11
    else:
        dh, df = (.06 if soft else .14), .16
    # Примечания к табл. 6, п. 6.1 и табл. 13, п. 3 относятся к массивной детали.
    inertia_factor = (1 + u*u) * gamma / (u*u + gamma) if gamma > 1 else 1.
    multiplier = inertia_factor * g0 * v * math.sqrt(aw / u)
    return dict(g0=g0, limit=limit, deltaH=dh, deltaF=df, massFactor=inertia_factor,
                wH=min(limit, dh * multiplier), wF=min(limit, df * multiplier))


def resonant_factor(state, config, overlap, stiffness, width, force, ka, running_in, h_limits):
    """Таблицы 25–26. Возвращает единый Kv для контакта и изгиба."""
    zone = state['zone']
    if zone not in ('resonant', 'transition', 'supercritical') or overlap <= 1:
        raise ValueError('Таблица 26 требует εγ>1 и n₁/nE1≥0,85')
    if not {'pitchError', 'profileError'} <= config.keys():
        raise MissingDynamicMeasurements('Для приложения 5 задайте погрешности шага fpb и профиля ff в мкм')
    if running_in < 0 or min(config['pitchError'], config['profileError']) < running_in:
        raise ValueError('Приработка yα должна лежать между нулём и каждой исходной погрешностью')
    coeffs = {'Cv1': .32}
    if overlap <= 1.5:
        coeffs['Cv7'] = .75
    elif overlap < 2.5:
        coeffs['Cv7'] = .875 + .125 * math.sin(math.pi / 1.12 * (overlap - 1.96))
    else:
        coeffs['Cv7'] = 1.
    if overlap <= 2:
        if config.get('coefficients'):
            raise ValueError('При εγ≤2 значения Cv задаёт таблица 26')
        coeffs.update(Cv2=.34, Cv4=.90, Cv5=.47, Cv6=.47)
    else:
        required = set()
        if zone != 'supercritical':
            required.update(('Cv2', 'Cv4'))
        if zone != 'resonant':
            required.update(('Cv5', 'Cv6'))
        missing = required - config.get('coefficients', {}).keys()
        if missing:
            raise ValueError('При εγ>2 в доступном издании табл. 26 отсутствуют '
                             + ', '.join(sorted(missing)) + '. Для расчёта нужны значения с источником.')
        coeffs.update(config['coefficients'])
    load = _value(force, 'Ft') / _value(width, 'bᵥ')
    bp = stiffness * (config['pitchError'] - running_in) / (ka * load)
    bf = stiffness * (config['profileError'] - running_in) / (ka * load)
    ca = sum(1.5 + ((_value(s, 'σHlim') / 97 - 18.45)**2) / 18 for s in h_limits) / 2
    bk = 1 - abs(stiffness * ca / load)
    kr = ks = None
    if zone != 'supercritical':
        kr = 1 + coeffs['Cv1'] * bp + coeffs['Cv2'] * bf + coeffs['Cv4'] * bk
    if zone != 'resonant':
        ks = coeffs['Cv5'] * bp + coeffs['Cv6'] * bf + coeffs['Cv7']
    if zone == 'transition':
        kv = ks + (kr - ks) * (1.5 - state['ratio']) / .35
    else:
        kv = kr if zone == 'resonant' else ks
    _value(kv, 'Kv по табл. 25')
    return dict(Kv=kv, Bp=bp, Bf=bf, BK=bk, Ca=ca, Cv=coeffs, resonant=kr, supercritical=ks)
