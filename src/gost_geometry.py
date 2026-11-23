"""Геометрия внешней эвольвентной пары с исходным углом 20°.

ГОСТ 21354–87, приложение 2, таблица 20. Углы на границе API в градусах,
длины в мм, частота в об/мин. Для шеврона width — рабочая ширина полушеврона.
"""
import math


def _number(value, label):
    try:
        finite = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f'{label} должно быть конечным числом')


def _involute(angle):
    return math.tan(angle) - angle


def _working_angle(alpha_t, shift, teeth):
    if shift == 0:
        return alpha_t
    target = _involute(alpha_t) + 2 * shift * math.tan(math.radians(20)) / teeth
    if target <= 0 or not math.isfinite(target):
        raise ValueError('Сумма смещений не даёт положительного рабочего угла зацепления')
    # inv α непрерывно возрастает от нуля до бесконечности.
    low, high = 0., math.pi / 2
    for _ in range(64):
        mid = (low + high) / 2
        if _involute(mid) < target:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def external_geometry(m, z1, z2, beta, width, speed, x1=0, x2=0):
    """Таблица 20, пп. 1–10. Диаметры вершин принимаются по п. 5.

    a — делительное межосевое, aW — рабочее. Для прямых зубьев pX=None,
    εβ=0. Знак β обозначает направление зубьев шестерни и сохраняется в βb.
    """
    for value, label in ((m, 'm'), (z1, 'z₁'), (z2, 'z₂'), (beta, 'β'),
                         (width, 'bᵥ'), (speed, 'n₁'), (x1, 'x₁'), (x2, 'x₂')):
        _number(value, label)
    if min(m, width, speed) <= 0:
        raise ValueError('Модуль, рабочая ширина и частота вращения должны быть положительными')
    if any(z < 1 or z != int(z) for z in (z1, z2)):
        raise ValueError('Числа зубьев должны быть положительными целыми')
    if abs(beta) >= 90:
        raise ValueError('Модуль угла наклона должен быть меньше 90°')
    beta_rad = math.radians(beta)
    cos_beta, sin_beta = math.cos(beta_rad), abs(math.sin(beta_rad))
    an = math.radians(20)
    at = math.atan(math.tan(an) / cos_beta)
    atw = _working_angle(at, x1 + x2, z1 + z2)
    a = m * (z1 + z2) / (2 * cos_beta)
    aw = a * math.cos(at) / math.cos(atw)
    result = dict(m=m, z1=z1, z2=z2, beta=beta, bWidth=width, speed=speed,
                  x1=x1, x2=x2, alphaT=math.degrees(at), alphaTW=math.degrees(atw),
                  betaB=math.degrees(math.asin(math.sin(beta_rad) * math.cos(an))),
                  a=a, aW=aw, u=z2 / z1)
    for i, (z, x) in enumerate(((z1, x1), (z2, x2)), 1):
        d = m * z / cos_beta
        db = d * math.cos(at)
        dw = db / math.cos(atw)
        da = d + 2 * m * (1 + x)
        if da <= db:
            raise ValueError(f'Колесо {i}: диаметр вершин должен превышать основной диаметр')
        aa = math.acos(db / da)
        epsilon = z * (math.tan(aa) - math.tan(atw)) / (2 * math.pi)
        if epsilon <= 0:
            raise ValueError(f'Колесо {i}: полюс зацепления выходит за рабочий профиль')
        tip_thickness = da * ((math.pi / 2 + 2 * x * math.tan(an)) / z
                              + _involute(at) - _involute(aa))
        if tip_thickness <= 0:
            raise ValueError(f'Колесо {i}: эвольвентные профили пересекаются до окружности вершин')
        for name, value in (('d', d), ('dw', dw), ('da', da), ('db', db),
                            ('alphaA', math.degrees(aa)), ('epsilonA', epsilon),
                            ('zv', z / cos_beta ** 3), ('tipThickness', tip_thickness)):
            result[f'{name}{i}'] = value
    # Действительная линия зацепления должна лежать между точками касания
    # общей касательной с основными окружностями обоих колёс.
    base_pitch = math.pi * m * math.cos(at) / cos_beta
    for i, mate in ((1, 2), (2, 1)):
        if result[f'epsilonA{mate}'] * base_pitch > result[f'db{i}'] / 2 * math.tan(atw):
            raise ValueError(f'Колесо {i}: контакт выходит за точку касания основной окружности')
    result['epsilonAlpha'] = result['epsilonA1'] + result['epsilonA2']
    result['pX'] = math.pi * m / sin_beta if sin_beta else None
    result['epsilonBeta'] = width * sin_beta / (math.pi * m)
    result['epsilonGamma'] = result['epsilonAlpha'] + result['epsilonBeta']
    result['v'] = math.pi * result['d1'] * speed / 60000
    if any(value is not None and not math.isfinite(value) for value in result.values()):
        raise ValueError('Геометрия выходит за диапазон конечных чисел')
    return result


def pair_stiffness(zv1, zv2, x1=0, x2=0):
    """Удельная нормальная жёсткость c′, Н/(мм·мкм), табл. 6, п. 7.1.2."""
    for value, label in ((zv1, 'zᵥ₁'), (zv2, 'zᵥ₂'), (x1, 'x₁'), (x2, 'x₂')):
        _number(value, label)
    if min(zv1, zv2) <= 0:
        raise ValueError('Эквивалентные числа зубьев должны быть положительными')
    compliance = (.05139 + .1425 / zv1 + .1860 / zv2
                  - .01 * x1 - .1027 * x1 / zv1
                  + .00455 * x2 + .3762 * x2 / zv2
                  + .00734 * x1 * x1 - .00054 * x2 * x2)
    if compliance <= 0 or not math.isfinite(compliance):
        raise ValueError('Формула табл. 6, п. 7.1.2 не даёт положительной конечной жёсткости')
    return 1 / compliance


def tooth_form_factor(zv, x=0, tool='standard'):
    """Приближённый YFS, табл. 13, п. 6. Шлифовочная ступенька не учитывается."""
    _number(zv, 'zᵥ')
    _number(x, 'x')
    if zv <= 0:
        raise ValueError('Эквивалентное число зубьев должно быть положительным')
    if tool == 'standard':
        factor = 3.47 + (13.2 - 29.7 * x) / zv + .092 * x * x
    elif tool == 'protuberance':
        # Для hₐ₀/m = 1,4 и Pᵣ₀/m = 0,05 в табл. 13 дана отдельная зависимость.
        factor = 3.61 + .53 * x * x + (25.3 - 37.6 * x) / zv
    else:
        raise ValueError('Выберите стандартный инструмент или инструмент с протуберанцем по табл. 13')
    if not math.isfinite(factor) or factor <= 0:
        raise ValueError('Формула табл. 13, п. 6 не даёт положительного конечного YFS')
    return factor
