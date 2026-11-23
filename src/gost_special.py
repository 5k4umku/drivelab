"""Уточнённые расчёты внешнего зацепления. ГОСТ 21354–87, приложения 7 и 9."""
import math


def _numbers(**values):
    for key, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f'{key} должно быть конечным числом')


def _positive(**values):
    _numbers(**values)
    for key, value in values.items():
        if value <= 0:
            raise ValueError(f'{key} должно быть положительным')


def _profile_geometry(z1, z2, alpha_tw, db1, db2, da1, da2):
    _positive(z1=z1, z2=z2, alpha_tw=alpha_tw, db1=db1, db2=db2, da1=da1, da2=da2)
    if not (int(z1) == z1 and int(z2) == z2 and alpha_tw < 90):
        raise ValueError('Требуются целые числа зубьев и угол зацепления от 0 до 90°')
    if not math.isclose(db1 / z1, db2 / z2, rel_tol=1e-7):
        raise ValueError('Основной шаг шестерни и колеса должен совпадать')
    if da1 <= db1 or da2 <= db2:
        raise ValueError('Окружности вершин должны лежать выше основных окружностей')
    tw = math.tan(math.radians(alpha_tw))
    ta1 = math.sqrt((da1 / db1)**2 - 1)
    ta2 = math.sqrt((da2 / db2)**2 - 1)
    ea1 = z1 * (ta1 - tw) / math.tau
    ea2 = z2 * (ta2 - tw) / math.tau
    if min(ea1, ea2) <= 0 or ea1 + ea2 < 1:
        raise ValueError('Проверьте непрерывность зацепления и положение полюса на активном профиле')
    return tw, ta1, ta2, ea1, ea2


def helical_allowable(*, z1, z2, alpha_tw, db1, db2, da1, da2,
                     hp1, hp2, hb1, hb2, hv1, hv2, velocity):
    """Формула (46), таблица 28. Твёрдости HB и HV задаются независимо."""
    _positive(hp1=hp1, hp2=hp2, hb1=hb1, hb2=hb2, hv1=hv1, hv2=hv2, velocity=velocity)
    if velocity > 25:
        raise ValueError('Окружная скорость превышает область ГОСТ 21354–87')
    tw, _, _, ea1, ea2 = _profile_geometry(z1, z2, alpha_tw, db1, db2, da1, da2)
    u = z2 / z1
    ki, kii = (math.tau * ea / (z1 * tw) for ea in (ea1, ea2))
    di = 1 + ki / 2 - ki / (2 * u) - ki**2 / (3 * u)
    dii = 1 - kii / 2 + kii / (2 * u) - kii**2 / (3 * u)
    if min(di, dii) <= 0 or ki > u or kii > 1:
        raise ValueError('Активный участок выходит за область контакта эвольвент')
    mu1, mu2 = (1.6 * (200 / max(200, hb))**0.25 for hb in (hb1, hb2))
    raw_i, raw_ii = min(mu1 * hp1, hp2), min(hp1, mu2 * hp2)
    phi = None
    if raw_i != raw_ii:
        if max(hv1, hv2) <= 350:
            phi = math.sqrt(2.7 - 0.1 * velocity) if velocity < 15 else 1.12
        elif min(hv1, hv2) > 350:
            phi = math.sqrt(1.9 - 0.1 * velocity) if velocity < 9 else 1.0
        else:
            raise ValueError('Для пары по разные стороны 350 HV таблица 28 не задаёт φP при разных допускаемых напряжениях зон')
    limit = min(raw_i, raw_ii) * phi if phi is not None else raw_i
    hp_i, hp_ii = min(raw_i, limit), min(raw_ii, limit)
    hp = math.sqrt((ea1 * di * hp_i**2 + ea2 * dii * hp_ii**2) / (ea1 + ea2))
    return dict(HP=hp, epsilonAlpha1=ea1, epsilonAlpha2=ea2, KI=ki, KII=kii,
                deltaI=di, deltaII=dii, muK1=mu1, muK2=mu2, phiP=phi,
                rawI=raw_i, rawII=raw_ii, hpI=hp_i, hpII=hp_ii)


# Коэффициенты даны в порядке одночленов таблицы 33.
# В напечатанном выражении YFS модифицированного профиля член +3,646xξ².
_FLEXIBILITY = {
    'standard': (9.671, -7.521, 1.626, -.041, -3.878, 4.662, -.457,
                 1.557, -.734, -.224, -3.440, 2.674, -.515, -2.180,
                 -.737, .338, 2.042, -.298, .529, -.573),
    'modified': (12.280, -6.077, .886, -.033, -4.489, 3.800, -.214,
                 1.113, -.599, -.079, -10.207, 1.536, -.242, 1.250,
                 -.516, -.138, 4.389, -.008, -.155, -.807),
}
_SHAPE = {
    'standard': (7.103, -5.683, .687, -.100, -3.737, 4.461, -.278,
                 1.221, -.862, -.115, -1.163, .497, -.012, -.579,
                 -.161, .170, .192, -.078, -.127, .221),
    'modified': (9.003, -4.814, .285, -.051, -5.908, 3.646, -.097,
                 2.231, -.687, -.282, -1.657, .412, -.005, -.182,
                 -.137, .079, .232, -.041, -.125, .162),
}


def _polynomial(coef, z, x, h, squared_cross=False):
    q = math.log10(z)
    terms = (1, x, x**2, x**3, q, x*q**2 if squared_cross else x*q, x**2*q,
             q**2, x*q**2, q**3, h, x*h, x**2*h, q*h, x*q*h, q**2*h,
             h**2, x*h**2, q*h**2, h**3)
    value = math.fsum(a * b for a, b in zip(coef, terms))
    if value <= 0 or not math.isfinite(value):
        raise ValueError('Полином таблицы 33 дал нефизическое значение. Проверьте геометрию зуба')
    return value


def _height(ta, t, diameter, module):
    if t < 0 or t > ta + 1e-12:
        raise ValueError('Расчётная точка находится вне активного эвольвентного профиля')
    return max(0, (math.hypot(1, ta) - math.hypot(1, t)) * diameter / (2 * module))


def spur_bending(*, z1, z2, x1, x2, module, alpha_tw, db1, db2, da1, da2,
                 df1, df2, width, force, ka, khv, khbeta, kfv, kfbeta, fpb1, fpb2,
                 accuracy, profile='standard', approximation=False):
    """Приложение 9. σF в МПа, FtF в Н, fpb в мкм, размеры в мм, αtw в градусах."""
    _positive(module=module, width=width, force=force, df1=df1, df2=df2)
    _numbers(x1=x1, x2=x2, ka=ka, khv=khv, khbeta=khbeta, kfv=kfv, kfbeta=kfbeta,
             fpb1=fpb1, fpb2=fpb2, accuracy=accuracy)
    if not 1 <= accuracy <= 8 or accuracy != int(accuracy):
        raise ValueError('Уточнение по табл. 13, п. 5 требует степень точности по плавности не грубее 8')
    if module < 1 or min(ka, khv, khbeta, kfv, kfbeta) < 1 or min(fpb1, fpb2) < 0:
        raise ValueError('Требуются m≥1 мм, коэффициенты нагрузки ≥1 и неотрицательные погрешности шага')
    if profile not in _SHAPE or not isinstance(approximation, bool):
        raise ValueError('Укажите профиль standard или modified и логическое значение approximation')
    if df1 >= da1 or df2 >= da2:
        raise ValueError('Диаметр впадин должен быть меньше диаметра вершин')
    tw, ta1, ta2, ea1, ea2 = _profile_geometry(z1, z2, alpha_tw, db1, db2, da1, da2)
    if not 1 < ea1 + ea2 < 2:
        raise ValueError('Для сравнения одно- и двухпарного контакта требуется 1 < εα < 2')
    pitch_error = math.hypot(fpb1, fpb2)
    stress_scale = force * ka * kfv * kfbeta / (width * module)
    cos_tw = math.cos(math.radians(alpha_tw))

    def member(z, x, ta, db, mate_z, mate_x, mate_ta, mate_db, mate_df):
        # Табл. 33 для вершины рассматриваемого зуба, затем табл. 34 для точки u.
        mate_tp = tw - z / mate_z * (ta - tw)
        tv = ta - math.tau / z
        mate_tu = mate_tp + math.tau / mate_z
        tu = tw - mate_z / z * (mate_ta - tw) + math.tau / z
        hu = _height(ta, tu, db, module)
        yfa = _polynomial(_SHAPE[profile], z, x, 0, profile == 'modified')
        yfu = _polynomial(_SHAPE[profile], z, x, hu, profile == 'modified')
        out = dict(hmu=hu, YFSa=yfa, YFSu=yfu)
        if approximation:
            kfa = .932 + .11 * pitch_error / (force / width)
        else:
            hp = _height(mate_ta, mate_tp, mate_db, module)
            hv = _height(ta, tv, db, module)
            # Для h_mu2 в табл. 33 напечатан d_f2, в табл. 34 для h_mu1 — d_b1.
            hmu_mate = _height(mate_ta, mate_tu, mate_df, module)
            flex = _FLEXIBILITY[profile]
            cp_a = 100 / (_polynomial(flex, z, x, 0) + _polynomial(flex, mate_z, mate_x, hp))
            cp_v = 100 / (_polynomial(flex, z, x, hv) + _polynomial(flex, mate_z, mate_x, hmu_mate))
            kfa = 2 * cp_a / (cp_a + cp_v) * (
                1 + .78 * width * cos_tw * cp_v * pitch_error / (force * ka * khv * khbeta))
            out.update(hmp=hp, hmv=hv, hmuMate=hmu_mate, caPrime=cp_a, cvPrime=cp_v)
        tip = .5 * kfa * yfa * stress_scale
        single = yfu * stress_scale
        return dict(**out, KFalphaA=kfa, tip=tip, single=single, sigmaF=max(tip, single),
                    governing='tip' if tip > single else 'single')

    pinion = member(z1, x1, ta1, db1, z2, x2, ta2, db2, df2)
    wheel = member(z2, x2, ta2, db2, z1, x1, ta1, db1, df1)
    return dict(pinion=pinion, wheel=wheel, sigmaF=[pinion['sigmaF'], wheel['sigmaF']],
                epsilonAlpha=ea1+ea2, approximation=approximation)
