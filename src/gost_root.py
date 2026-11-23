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
        if x != 0:
            raise ValueError('Для черт. 12а при x≠0 требуется измеренный радиус')
        ratio = .417 + 4.32 / zv
    else:
        ratio = .424 + (7.27 - 16.8*x + 9.81*x*x) / zv - .019*x - .004*x*x
    return _number(module*ratio, 'радиуса по черт. 12')


def root_parameters(config, *, module, zv, x, tool, material_row, yield_strength, spur):
    """Fatigue support factor for one documented root section (table 13.12)."""
    _number(module, 'mn')
    keys = {'radiusMm', 'uncertaintyMm', 'section', 'evidence', 'curveConfirmed',
            'materialEvidence', 'baseHardened', 'grindingStep', 'toolProfile', 'yieldStrength'}
    if not isinstance(config, dict) or set(config) - keys:
        raise ValueError('Неизвестный формат описания корня или неподтверждённая поправка')
    if config.get('grindingStep', False) is not False:
        raise ValueError('Поправка на шлифовочную ступеньку требует отдельного обоснования')
    evidence = config.get('evidence')
    if not isinstance(evidence, str) or not evidence.strip():
        raise ValueError('Укажите протокол измерения или источник проверки номинального профиля')
    measured = 'radiusMm' in config
    if 'toolProfile' in config and (measured or tool != 'protuberance'):
        raise ValueError('Параметры инструмента 12б относятся только к номинальному радиусу по этому рисунку')
    if measured:
        section = config.get('section')
        if not isinstance(section, str) or not section.strip() or 'curveConfirmed' in config:
            raise ValueError('Укажите положение опасного сечения в нормальном профиле')
        radius = _number(config['radiusMm'], 'радиуса в мм')
        delta = _number(config.get('uncertaintyMm'), 'погрешности в мм', positive=False)
        if delta < 0 or radius - delta <= 0 or radius - delta <= 7 < radius + delta:
            raise ValueError('Интервал измерения должен быть положительным и однозначно определять ветвь порога 7 мм')
        source = f'{section}, погрешность ±{delta:g} мм'
    else:
        if (not spur or config.get('curveConfirmed') is not True
                or 'uncertaintyMm' in config or 'section' in config):
            raise ValueError('Нужна прямая пара и подтверждение инструмента и точки на соответствующей кривой черт. 12')
        if tool == 'protuberance':
            profile = config.get('toolProfile')
            required = dict(alphaDeg=20, haStar=1, clearanceStar=.4, radiusStar=.4, protuberanceStar=.05)
            if (profile != required or any(type(v) not in (int, float) for v in profile.values())):
                raise ValueError('Для черт. 12б подтвердите геометрию инструмента по чертежу')
        radius = nominal_radius(module, zv, x, tool)
        figure = '12а' if tool == 'standard' else '12б'
        source = f'черт. {figure}, z={zv:g}, x={x:g}'
    grad = 2.3/radius
    branch = 'radiusAtMost7'
    value = 1.082 - .172*math.log10(module)
    formula = 'Yδ=1,082−0,172 lg(mn)'
    material_source = config.get('materialEvidence', '')
    if not isinstance(material_source, str):
        raise ValueError('Источник подтверждения материала должен быть текстом')
    if 'yieldStrength' in config and material_row != 'Т1':
        raise ValueError('Для табличного паспорта задайте σт в самом паспорте материала')
    if radius > 7:
        if material_row == 'Т1' and not material_source.strip():
            raise ValueError('Подтвердите улучшение основания и предел текучести по паспорту материала')
        hardened = material_row not in ('Т1', '16.1', '17.7')
        if (material_row.startswith('17.') or 'baseHardened' in config) and config.get('baseHardened') is not hardened:
            raise ValueError('Подтвердите охват основания слоем в соответствии со строкой таблицы 17')
        if material_row in ('16.1', '17.7', 'Т1'):
            strength = _number(config.get('yieldStrength') if material_row == 'Т1' else yield_strength, 'предела текучести σт, МПа')
            value = (1-.07*math.log10(module))*(1+grad**.55*10**(-.47-strength/875))
            branch, formula = 'unhardenedRoot', 'Yδ=(1−0,07 lg mn)(1+χ⁰·⁵⁵·10^(−0,47−σт/875))'
            source += f', σт={strength:g} МПа'
        elif material_row in ('14.1','14.2','14.3','14.4','14.5','15.1','15.2',
                              '17.1','17.2','17.3','17.4','17.5','17.6'):
            value = .84*(1+grad**.55*10**-.72)
            branch, formula = 'hardenedRoot', 'Yδ=0,84(1+χ⁰·⁵⁵·10⁻⁰·⁷²)'
        else:
            raise ValueError('Для материала этой группы уточнение по табл. 13, п. 12 не установлено')
    return dict(radius=radius, radiusSource=source, gradient=grad, gradientBranch=branch,
                Ydelta=value, formula=formula, evidence=evidence, materialRow=material_row,
                materialEvidence=material_source)


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
