"""Переходная кривая зуба, ГОСТ 21354–87, табл. 13 пп. 6, 12, черт. 10–12."""
import math


def _number(value, name, positive=True):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or (positive and value <= 0)):
        raise ValueError(f'Недопустимое значение {name}')
    return value


def measured_radius(points):
    """Радиус окружности через три точки нормального сечения, мм."""
    if not isinstance(points, (list, tuple)) or len(points) != 3:
        raise ValueError('Для оценки радиуса нужны три соседние точки нормального сечения')
    for pt in points:
        if not isinstance(pt, (list, tuple)) or len(pt) != 2:
            raise ValueError('Каждая точка должна содержать координаты x и y в мм')
        for coordinate in pt:
            _number(coordinate, 'координаты профиля', positive=False)
    p, q, r = points
    a, b, c = math.dist(q,r), math.dist(p,r), math.dist(p,q)
    cross = abs((q[0]-p[0])*(r[1]-p[1]) - (q[1]-p[1])*(r[0]-p[0]))
    if not min(a,b,c) or cross <= 1e-12*max(a,b,c)**2:
        raise ValueError('Окружность по совпадающим или коллинеарным точкам неопределима')
    return _number(a*b*c / (2*cross), 'радиуса по трём точкам')


def nominal_radius(module, zv, x, tool):
    """ρFn из зависимостей под черт. 12а, 12б для эквивалентного прямого зуба."""
    _number(module, 'mn')
    _number(zv, 'zv')
    _number(x, 'x', positive=False)
    if tool not in ('standard','protuberance'):
        raise ValueError('Для черт. 12 требуется стандартный инструмент или инструмент с протуберанцем')
    min_z, max_x = (12, 1.2) if tool == 'standard' else (14, 1.4)
    if not min_z <= zv <= 500 or not -.6 <= x <= max_x:
        raise ValueError('Параметры вне диапазона черт. 12. Введите измеренный радиус переходной кривой')
    if tool == 'standard':
        ratio = .417 + (4.32 - 10.34*x + 6.03*x*x) / zv - .071*x + .036*x*x
    else:
        ratio = .424 + (7.27 - 16.8*x + 9.81*x*x) / zv - .019*x - .004*x*x
    return _number(module*ratio, 'радиуса по черт. 12')


def _test_ratio(test, label):
    if not isinstance(test, dict) or set(test) != {'actualStress','referenceStress'}:
        raise ValueError(f'{label}: нужны local-напряжения actualStress и referenceStress в одинаковых условиях')
    return _number(test['actualStress'], 'σ фактического корня') / _number(test['referenceStress'], 'σ базового корня')


def root_parameters(config, *, module, zv, x, tool, material_row, yield_strength):
    """Опциональная поправка к YFS и уточнение Yδ для отдельного венца."""
    _number(module, 'mn')
    out = dict(tipFactor=1., singleFactor=1., radius=None, radiusSource=None, gradient=None,
               grindingStep=False, evidence='', Ydelta=1.082-.172*math.log10(module),
               gradientBranch='basic', formula='Yδ=1,082−0,172 lg(mn)')
    if config is None:
        return out
    if not isinstance(config, dict):
        raise ValueError('Для корня требуется объект с параметрами')
    keys = {'grindingStep','refineGradient','pointsMm','radiusMm','tipTest','singleTest','evidence'}
    if set(config)-keys:
        raise ValueError('Неизвестные поля геометрии корня: '+', '.join(sorted(set(config)-keys)))
    step = config.get('grindingStep', False)
    refine = config.get('refineGradient', False)
    if not isinstance(step, bool) or not isinstance(refine, bool):
        raise ValueError('Признаки ступеньки и уточнения градиента должны быть логическими')
    measured = 'pointsMm' in config or 'radiusMm' in config
    evidence = config.get('evidence', '')
    if not isinstance(evidence, str) or ((step or measured) and not evidence.strip()):
        raise ValueError('Укажите источник измерений радиуса или напряжений в корне')
    out['evidence'] = evidence
    if step:
        out.update(grindingStep=True, tipFactor=_test_ratio(config.get('tipTest'), 'tipTest'),
                   singleFactor=_test_ratio(config['singleTest'], 'singleTest') if 'singleTest' in config else None)
    elif 'tipTest' in config or 'singleTest' in config:
        raise ValueError('Измерения для шлифовочной ступеньки требуют grindingStep=true')
    if 'pointsMm' in config and 'radiusMm' in config:
        raise ValueError('Выберите один источник радиуса: результат измерения или три точки')
    if measured:
        if 'pointsMm' in config:
            out.update(radius=measured_radius(config['pointsMm']), radiusSource='три точки профиля')
        else:
            out.update(radius=_number(config['radiusMm'], 'ρFn'), radiusSource='протокол измерения')
    elif refine:
        if step:
            raise ValueError('Для градиента в корне со ступенькой требуется фактический ρFn')
        out.update(radius=nominal_radius(module,zv,x,tool), radiusSource='черт. 12а' if tool=='standard' else 'черт. 12б')
    if not refine:
        return out
    radius = out['radius']
    out['gradient'] = grad = 2.3/radius
    if radius <= 7:
        out['gradientBranch'] = 'radiusAtMost7'
    elif material_row in ('Т1','16.1','17.7'):
        yield_strength = _number(yield_strength, 'предела текучести σт, МПа')
        out.update(Ydelta=(1-.07*math.log10(module))*(1+grad**.55*10**(-.47-yield_strength/875)),
                   gradientBranch='unhardenedRoot', formula='Yδ=(1−0,07 lg mn)(1+χ⁰·⁵⁵·10^(−0,47−σт/875))')
    elif material_row.startswith(('14.','15.','17.')):
        out.update(Ydelta=.84*(1+grad**.55*10**-.72), gradientBranch='hardenedRoot',
                   formula='Yδ=0,84(1+χ⁰·⁵⁵·10⁻⁰·⁷²)')
    else:
        out['gradientBranch'] = 'materialWithoutRefinement'
    return out


def correct_spur_phases(result, roots):
    """Дополнительные подтверждённые коэффициенты по п. 3 для каждой фазы."""
    for i, (key, root) in enumerate(zip(('pinion', 'wheel'), roots)):
        if not root['grindingStep']:
            continue
        if root['singleFactor'] is None:
            raise ValueError('Для ступеньки в приложении 9 задайте singleTest для верхней граничной точки')
        item = result[key]
        item['YFSa'] *= root['tipFactor']
        item['YFSu'] *= root['singleFactor']
        item['tip'] *= root['tipFactor']
        item['single'] *= root['singleFactor']
        item['sigmaF'] = result['sigmaF'][i] = max(item['tip'],item['single'])
        item['governing'] = 'tip' if item['tip'] > item['single'] else 'single'
    return result
