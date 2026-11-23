"""Глубинное разрушение зуба. ГОСТ 21354–87, приложение 8, стр. 93–99."""
import math
from bisect import bisect_left


def _positive(**values):
    for key, value in values.items():
        if (not isinstance(value, (int, float)) or isinstance(value, bool)
                or not math.isfinite(value) or value <= 0):
            raise ValueError(f'{key} должно быть конечным положительным числом')


def reduced_radius(d1, u, beta_deg):
    """Таблица 29, п. 3.2, результат в мм."""
    _positive(d1=d1, u=u)
    if isinstance(beta_deg, bool) or not isinstance(beta_deg, (int, float)) or not -90 < beta_deg < 90:
        raise ValueError('Требуется угол наклона зуба в градусах от −90 до 90')
    return .17 * d1 * u / ((u+1) * math.cos(math.radians(beta_deg))**2)


def _interpolate(x, points):
    """Линейная интерполяция только между оцифрованными точками."""
    xs = [k for k, _ in points]
    if not xs[0] <= x <= xs[-1]:
        raise ValueError('Точка за пределами оцифрованных кривых')
    i = bisect_left(xs, x)
    if xs[i] == x:
        return points[i][1]
    x0, y0 = points[i-1]
    x1, y1 = points[i]
    return y0 + (y1-y0) * (x-x0) / (x1-x0)


# Чертёж 29а: φ, Aφ. Чертёж 29б: H0/HK, затем пары (φ, μT).
_A_PHI = ((0, 5.20), (.5, 5.23), (.75, 5.30), (1, 5.59), (1.5, 6.32),
          (2, 6.97), (2.5, 7.58), (3, 8.16), (3.5, 8.70), (4, 9.22),
          (4.5, 9.71), (5, 10.18), (5.5, 10.61), (5.9, 10.98))
_MU_T = (
    (1.2, ((1.1, 1), (2, .939), (3, .880), (4, .827), (5, .779), (6, .739))),
    (2.2, ((1.5, 1), (2, .976), (3, .933), (4, .896), (5, .865), (6, .839))),
    (2.6, ((2.5, 1), (3, .988), (4, .968), (5, .952), (6, .941))),
)


def nitriding_graphs(phi, ratio):
    a = _interpolate(phi, _A_PHI)
    ratios = [key for key, _ in _MU_T]
    if not ratios[0] <= ratio <= ratios[-1]:
        raise ValueError('Отношение H0/HK выходит за пределы черт. 29б')
    i = bisect_left(ratios, ratio)
    if ratios[i] == ratio:
        return a, _interpolate(phi, _MU_T[i][1])
    return a, _interpolate(ratio, [(k, _interpolate(phi, curve)) for k, curve in _MU_T[i-1:i+1]])


# Чертёж 30: для каждой прямой считаны K/10⁶ при D=0 и D=200.
# Верхняя кривая на чертеже подписана отдельно; здесь используем диапазон
# 2500–4000 МПа, где шкалу и интервалы можно однозначно восстановить.
_FIGURE_30 = ((2500, 15.7, 3.0), (2750, 20.7, 5.7), (3000, 27.3, 9.0),
              (3250, 34.5, 13.2), (3500, 42.7, 18.4), (3750, 52.7, 24.3),
              (4000, 63.9, 32.0))


def boundary_from_chart(core_hv, thickness, rho):
    """Интерполяция по прямым черт. 30. Возвращает обе соседние изолинии."""
    _positive(core_hv=core_hv, thickness=thickness, rho=rho)
    d = .42 * core_hv
    k = 1.6 * core_hv * (thickness/rho)**2
    if d > 200:
        raise ValueError('D превышает шкалу чертежа 30')
    lines = [(k0+(k200-k0)*d/200, s) for s, k0, k200 in _FIGURE_30]
    stress = _interpolate(k, lines)
    i = bisect_left([point for point, _ in lines], k)
    lower = lines[i][1] if k == lines[i][0] else lines[i-1][1]
    return dict(value=stress, lower=lower, upper=lines[i][1], D=d, K=k*1e6)


def profile_hardness(treatment, surface_hv, core_hv, relative_depth):
    """Требуемое H(z) для 0≤z/ht≤1, формулы (49), (50), HV."""
    _positive(surface_hv=surface_hv, core_hv=core_hv)
    if surface_hv < core_hv:
        raise ValueError('Твёрдость поверхности должна быть не ниже твёрдости сердцевины')
    if isinstance(relative_depth, bool) or not isinstance(relative_depth, (int, float)) or not 0 <= relative_depth <= 1:
        raise ValueError('Глубина должна принадлежать упрочнённому слою')
    if treatment == 'nitrided':
        return surface_hv + (surface_hv-core_hv)*relative_depth*(.8*relative_depth-1.8)
    if treatment in ('carburized', 'carbonitrided'):
        return surface_hv / (1 + (surface_hv/core_hv-1) * relative_depth**2)
    raise ValueError('Приложение 8 применяется к азотированию, цементации или нитроцементации')


_SAFETY = {
    ('carbon', True): 1.5,
    ('low_alloy', True): 1.4, ('low_alloy', False): 1.5,
    ('nickel_below_1', True): 1.3, ('nickel_below_1', False): 1.4,
    ('nickel_chromium_above_1', True): 1.2,
}


def deep_contact(*, treatment, surface_hv, core_hv, thickness, rho, sigma_h, profile_confirmed,
                 line_load=None, elastic_modulus=None, peak_ratio=None, sigma_max=None,
                 confirmed_depth=None, steel_group=None, controlled=None, cycles=None,
                 safety=None, peak_safety=1.1, boundary_mpa=None):
    """Один венец. Единицы: мм, Н/мм, МПа, HV и циклы. Для второго венца вызывают отдельно.

    Без независимой hH возвращает предварительные глубины и неопределённый
    исход ветвей, зависящих от глубины. См. docs/gost-subsurface.md.
    """
    _positive(core_hv=core_hv, surface_hv=surface_hv, thickness=thickness, rho=rho, sigma_h=sigma_h)
    profile_hardness(treatment, surface_hv, core_hv, 0)
    if not isinstance(profile_confirmed, bool) or (controlled is not None and not isinstance(controlled, bool)):
        raise ValueError('Подтверждения профиля и автоматического регулирования должны быть логическими')
    if safety is None:
        safety = 1.4 if treatment == 'nitrided' else _SAFETY.get((steel_group, controlled))
        if safety is None:
            raise ValueError('Задайте обоснованный SHK либо сочетание стали и регулирования из табл. 31')
    _positive(safety=safety)
    if safety < 1:
        raise ValueError('SHK должен быть не меньше 1')
    warnings = []
    if not profile_confirmed:
        warnings.append('Требуется подтверждение распределения твёрдости по толщине слоя по (49) или (50).')

    def effective_hv(depth):
        return surface_hv / (1 + (surface_hv/core_hv-1) * ((depth+.2)/thickness)**2)

    def result(stress, limits, sf, can_check):
        if not limits:
            return dict(stress=stress, allowable=None, margin=None, passed=None, zone=None, limits={})
        zone = min(limits, key=limits.get)
        allowable = limits[zone] / sf
        return dict(stress=stress, allowable=allowable, margin=allowable/stress, zone=zone,
                    passed=(stress <= allowable) if can_check and profile_confirmed else None,
                    limits=limits)

    aux = dict(rho=rho, SHK=safety)
    fatigue_limits = {}
    if treatment == 'nitrided':
        _positive(cycles=cycles)
        base = (.0133*core_hv-1)*1e7
        if base <= 0:
            raise ValueError('Базовое число глубинных циклов получается неположительным')
        zlk = max(1., (base/cycles)**(1/18))
        phi = thickness*1e4/(rho*core_hv)
        aux.update(NHK=base, NEK=cycles, ZLK=zlk, phi=phi)
        try:
            a, mu = nitriding_graphs(phi, surface_hv/core_hv)
            fatigue_limits['nitrided'] = 1.07*a*mu*core_hv*zlk
            aux.update(Aphi=a, muT=mu)
        except ValueError:
            warnings.append('Черт. 29. Для заданных φ и H0/HK отсутствуют оцифрованные кривые.')
        fatigue = result(sigma_h, fatigue_limits, safety, True)
        # Приложение 1, п. 1.5.4 относит проверку (54) только к цементации
        # и нитроцементации. Для азотирования достаточно условия (47).
        return dict(fatigue=fatigue, peak=None, parameters=aux, warnings=warnings,
                    complete=fatigue['passed'] is not None)

    _positive(line_load=line_load, elastic_modulus=elastic_modulus, peak_ratio=peak_ratio,
              sigma_max=sigma_max, peak_safety=peak_safety)
    if peak_ratio < 1 or peak_safety < 1:
        raise ValueError('Tmax/TH и SHKSt должны быть не меньше 1')
    if confirmed_depth is not None:
        _positive(confirmed_depth=confirmed_depth)
    if boundary_mpa is not None:
        _positive(boundary_mpa=boundary_mpa)
    # В печати табл. 29.3 ρv расположен за чертой радикала. Даём обе
    # численные трактовки, исключая итоговый допуск по неоднозначной глубине.
    printed_h = 1.52 * math.sqrt(line_load/elastic_modulus) * rho
    dimensional_h = 1.52 * math.sqrt(line_load*rho/elastic_modulus)
    h = confirmed_depth if confirmed_depth is not None else dimensional_h
    h_peak = h * math.sqrt(peak_ratio)
    aux.update(hH=h, hHSt=h_peak, printedDepth=printed_h, dimensionalDepth=dimensional_h,
               SHKSt=peak_safety)
    if confirmed_depth is None:
        warnings.append('Табл. 29, п. 3. Уточните hH по независимому расчёту. В скане положение ρv относительно корня даёт размерность, отличную от мм.')
    if h > thickness:
        fatigue_limits['core'] = 3.6 * core_hv
    else:
        fatigue_limits.update(layer=3.6*effective_hv(h), boundary=core_hv*(.8*(thickness/h)**2+2.8))
    fatigue = result(sigma_h, fatigue_limits, safety, confirmed_depth is not None)

    peak_limits = {}
    chart = None
    if h_peak > thickness:
        peak_limits['core'] = 7.2 * core_hv
    else:
        if boundary_mpa is None:
            try:
                chart = boundary_from_chart(core_hv, thickness, rho)
                boundary_mpa = chart['value']
            except ValueError:
                warnings.append('Черт. 30. Для проверки границы слоя требуется самостоятельно считанное значение σHKSt, МПа.')
        if boundary_mpa is not None:
            peak_limits.update(layer=7.2*effective_hv(h_peak), boundary=boundary_mpa)
    peak = result(sigma_max, peak_limits, peak_safety, confirmed_depth is not None)
    if chart:
        aux['figure30'] = chart
        # Между соседними изолиниями сохраняем неопределённость исхода
        # проверки, если её знак зависит от интерполяции по чертежу.
        if min(peak_limits['layer'], chart['lower']) < sigma_max*peak_safety <= min(peak_limits['layer'], chart['upper']):
            peak['passed'] = None
            warnings.append('Условие (54) меняет знак между соседними изолиниями черт. 30. Уточните предельное напряжение.')
    return dict(fatigue=fatigue, peak=peak, parameters=aux, warnings=warnings,
                complete=fatigue['passed'] is not None and peak['passed'] is not None)
