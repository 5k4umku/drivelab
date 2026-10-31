"""Transparent restricted rating using GOST 21354-87 Appendix 1 equations.

This is not a certificate of full compliance. Material limits and face-load
factors come from explicit project inputs; shaft deflection is not calculated.
Scope: standard 20-degree rack, x1=x2=0, oil lubrication, steel U/U gears.
Units: mm, N, N*m, MPa, rpm. No third-party dependency.
"""
import math
from coefficients import face_factors

SOURCE = 'ГОСТ 21354-87, приложение 1'
PDF_URL = 'https://files.stroyinf.ru/Data2/1/4294832/4294832225.pdf'


def contact_life(n_base, n_equivalent, homogeneous=True):
    """Table 11.3, p.24: includes the post-knee twentieth-root branch."""
    if any(not isinstance(x,(int,float)) or isinstance(x,bool) or not math.isfinite(x) or x<=0 for x in (n_base,n_equivalent)):
        raise ValueError('Числа циклов должны быть положительными')
    if n_equivalent <= n_base:
        return min(2.6 if homogeneous else 1.8,
                   (n_base / n_equivalent) ** (1 / 6))
    return max(.75, (n_base / n_equivalent) ** (1 / 20))


def bending_life(n_equivalent, q=6, n_base=4e6):
    """Table 13.9, pp.32–33. Only q=6 or q=9 are defined here."""
    if any(not isinstance(x,(int,float)) or isinstance(x,bool) or not math.isfinite(x) or x<=0 for x in (n_base,n_equivalent)) or q not in (6, 9):
        raise ValueError('Некорректные циклы или показатель кривой усталости')
    return min(4 if q == 6 else 2.5,
               max(1, (n_base / n_equivalent) ** (1 / q)))


def normative_rating(p, c, b, T, step=None, check=None):
    """Validate imported JSON before evaluating the restricted rating profile."""
    def reject(reason):
        item = dict(title='Входные данные проверочного расчёта', status='pending', detail=reason)
        if check:
            check(item['title'], item['status'], reason)
        return dict(available=False, complete=False, reason=reason, trace=[], checks=[item])
    def number(value):
        try:
            return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        except (ValueError, OverflowError):
            return False
    if not isinstance(p, dict) or not isinstance(c, dict):
        return reject('Исходные данные и геометрия должны быть объектами JSON')
    if p.get('_tableMissing'):
        return reject('Выбранные модуль, диаметр или скорость выходят за область автоматической Т7. Для отдельного расчёта задайте обоснованные погрешности вручную и отключите Т7; область ГОСТ проверяется независимо.')
    cfg = p.get('gost', {})
    if not isinstance(cfg, dict):
        return reject('gost должен быть объектом JSON')
    positive_p = ('KA','startup','speed','life','muH','muF','SH','SF','ZR','YR','YA','YzSmall','YzLarge','KHbeta','KFbeta','sigmaH1','sigmaH2','sigmaF1','sigmaF2','NHG1','NHG2')
    positive_c = ('m','z1','z2','alphaT','d1','d2','da1','da2','epsilonAlpha','v','u')
    for obj, keys in ((p, positive_p), (c, positive_c)):
        for key in keys:
            if not number(obj.get(key)) or obj[key] <= 0:
                return reject(f'{key}: требуется конечное положительное число, не bool')
    for key in ('fpb1','fpb2'):
        if not number(p.get(key)) or p[key] < 0:
            return reject(f'{key}: требуется конечное неотрицательное число')
    for key, default in (('alpha',20),('x1',0),('x2',0),('accuracy',7),('peakCount',0)):
        if not number(p.get(key, default)):
            return reject(f'{key}: требуется конечное число')
    if not number(c.get('beta')) or not -45 < c['beta'] < 45:
        return reject('Угол β должен быть конечным числом в диапазоне −45…45°')
    if not number(b) or not number(T) or b <= 0 or T <= 0:
        return reject('Ширина и момент должны быть конечными положительными числами')
    flags = {'faceFactorsConfirmed','surfaceConfirmed','peakProbabilityFactorConfirmed','homogeneous','softSurface','oil','herringboneWidthIsTotal'}
    numbers = {'aAlpha','yAlpha','KHbeta','KFbeta','KHbeta0','peakProbabilityFactor','halfLoadShare','yield1','yield2'}
    for key, value in cfg.items():
        if key in flags:
            if not isinstance(value, bool):
                return reject(f'gost.{key}: требуется bool')
        elif key in numbers:
            if not number(value):
                return reject(f'gost.{key}: требуется конечное число, не bool')
            if key != 'yAlpha' and value <= 0 or key == 'yAlpha' and value < 0:
                return reject(f'gost.{key}: недопустимое неположительное значение')
        elif key == 'peakCycles':
            if value is not None and (not number(value) or value < 0 or value != int(value)):
                return reject('gost.peakCycles: требуется целое неотрицательное число или null')
        else:
            return reject(f'Неизвестный параметр gost.{key}')
    if p.get('peakCount',0) < 0 or p.get('peakCount',0) != int(p.get('peakCount',0)):
        return reject('peakCount: требуется целое неотрицательное число')
    if p['KA'] < 1 or p['SH'] < 1.1 or p['SF'] < 1.4 or p['YA'] > 1:
        return reject('Для профиля У: KA≥1, SH≥1.1, SF≥1.4, YA≤1')
    if cfg.get('peakProbabilityFactor',1.75) < 1 or cfg.get('KHbeta0',1) < 1:
        return reject('Sγ и KHβ0 должны быть не меньше1')
    if not cfg.get('homogeneous',True):
        return reject('Профиль У / У предполагает однородную структуру материала')
    for i in (1,2):
        if f'yield{i}' not in cfg:
            row = p.get(f'rowName{i}')
            if not isinstance(row,str) or not row.startswith('У') or not row[1:].isdigit() or int(row[1:]) <= 0:
                return reject(f'rowName{i}: требуется класс У с числовым пределом текучести')
    if any(c[key] != int(c[key]) for key in ('z1','z2')):
        return reject('Числа зубьев должны быть целыми')
    try:
        return _normative_rating(p,c,b,T,step,check)
    except (ArithmeticError, ValueError, KeyError, TypeError) as exc:
        return reject(f'Расчёт вне допустимой численной области: {type(exc).__name__}: {exc}')


def _normative_rating(p, c, b, T, step=None, check=None):
    """Return rating dict; optionally append to engine trace/check callbacks.

    p: engine inputs; optional p['gost'] config overrides:
      aAlpha=1, yAlpha=0 (declared conservative manufacturing assumptions),
      KHbeta/KFbeta (otherwise explicit seminar inputs),
      KHbeta0 (if known, permits Table13.4 calculation of KFbeta),
      faceFactorsConfirmed=False, surfaceConfirmed=False,
      homogeneous=True, softSurface=True, oil=True,
      peakCycles=None, peakProbabilityFactor=1.75,
      halfLoadShare=.5, herringboneWidthIsTotal=True.
    b is TOTAL active width (central groove excluded) for herringbone;
    use half width and specified load fraction, conservatively max(f,1-f).
    c: m,z1,z2,beta[degrees],alphaT[degrees],d1,d2,da1,da2,epsilonAlpha,v,u.
    Only x=0 and alphaN=20 are supported by the YFS approximation here.
    """
    cfg = p.get('gost', {})
    local_trace, local_checks = [], []
    def n(value):
        return f'{value:.9g}'
    def emit(title, formula, value, unit='', page='', substitution=''):
        source = f'{SOURCE}, {page}' if page else SOURCE
        substitution = substitution or f'Заданное значение: {n(value)}'
        local_trace.append(dict(title=title, formula=formula, value=value,
                                unit=unit, source=source, substitution=substitution))
        if step:
            step('7. Проверочный расчёт по формулам ГОСТ', title, formula,
                 substitution,
                 value, unit, source)
        return value
    def verify(title, status, detail):
        local_checks.append(dict(title=title, status=('pass' if status else 'fail')
                                 if isinstance(status, bool) else status, detail=detail))
        if check:
            check(title, status, detail)
    def rejected(message):
        verify('Область проверочного расчёта ГОСТ', 'pending', message)
        return dict(available=False, complete=False, reason=message,
                    trace=local_trace, checks=local_checks)

    gear_type = p.get('gearType', 'helical')
    if gear_type not in ('spur', 'helical', 'herringbone'):
        return rejected('Неизвестный тип передачи')
    if abs(p.get('alpha', 20) - 20) > 1e-9 or p.get('x1', 0) or p.get('x2', 0):
        return rejected('Приближение YFS реализовано для исходного контура 20° и x₁=x₂=0')
    if any(p.get(f'treatment{i}', 'У') != 'У' for i in (1, 2)):
        return rejected('Материальная модель этого профиля ограничена улучшенной сталью У / У')
    if p.get('mF',6) != 6:
        return rejected('Профиль улучшенной стали У / У использует показатель кривой изгибной усталости qF=6')
    if c['m'] < 1 or c['v'] > 25 or not cfg.get('oil', True):
        return rejected('Область ГОСТ: модуль ≥1 мм, v≤25 м/с, работа со смазкой маслом')
    m, beta, at, ea = c['m'], abs(math.radians(c['beta'])), math.radians(c['alphaT']), c['epsilonAlpha']
    expected_at = math.atan(math.tan(math.radians(20)) / math.cos(beta))
    if not math.isclose(at, expected_at, rel_tol=1e-8, abs_tol=1e-9):
        return rejected('αt не согласован с αn=20° и β; требуется пересчитать геометрию')
    for i in (1,2):
        if not math.isclose(c[f'd{i}'],m*c[f'z{i}']/math.cos(beta),rel_tol=1e-8) or not math.isclose(c[f'da{i}'],c[f'd{i}']+2*m,rel_tol=1e-8):
            return rejected('Диаметры не согласованы со стандартным контуром x=0')
    ea_expected = (sum(math.sqrt(c[f'da{i}']**2-(c[f'd{i}']*math.cos(at))**2)/2 for i in (1,2))-(c['d1']+c['d2'])/2*math.sin(at))/(math.pi*m/math.cos(beta)*math.cos(at))
    if not math.isclose(ea,ea_expected,rel_tol=1e-8):
        return rejected('εα не согласован с фактической геометрией')
    if not math.isclose(c['u'],c['z2']/c['z1'],rel_tol=1e-8):
        return rejected('Передаточное отношение не согласовано с числами зубьев')
    if not math.isclose(c['v'],math.pi*c['d1']*p['speed']/60000,rel_tol=1e-8):
        return rejected('Окружная скорость не согласована с диаметром и частотой вращения')
    if ea < 1 or b <= 0 or T <= 0 or c['u'] <= 0:
        return rejected('Требуются εα≥1 и положительные ширина, момент и отношение')
    if gear_type == 'spur' and beta > 1e-8:
        return rejected('Прямозубая передача должна иметь β=0')
    if gear_type != 'spur' and beta < 1e-8:
        return rejected('Для β=0 следует выбрать прямозубую передачу')
    helical = gear_type != 'spur'
    load_share = 1.
    face_width = b
    assumptions = [
        'Пределы усталости и базовые циклы материала заданы таблицей Т1 семинара.',
        'Коэффициенты по ширине заданы входами проекта; деформации валов и подшипников не вычислены.',
        'aα=1 и yα=0 — принятые консервативные допущения, если не заданы отдельно.',
        'Шероховатость и масляная смазка являются условиями проекта, не результатом измерения.',
        'Sγ=1,75 для оценки максимального изгиба принят как проектное допущение; указанное в табл.18 значение относится к материалам табл.19, а У / У использует приближение для отсутствующих в ней материалов.',
    ]
    if gear_type == 'herringbone':
        share = cfg.get('halfLoadShare', .5)
        if not 0 < share < 1 or not cfg.get('herringboneWidthIsTotal', True):
            return rejected('Для шеврона b — полная активная ширина, 0<доля нагрузки половины<1')
        face_width, load_share = b / 2, max(share, 1 - share)
        assumptions.append('Шеврон моделируется двумя косозубыми венцами; проверяется более нагруженная половина. Это явная расчётная модель распределения нагрузки.')
    Ft = 2000 * T / c['d1'] * load_share
    eb = face_width * math.sin(beta) / (math.pi * m)
    eg = ea + eb
    aw = (c['d1'] + c['d2']) / 2
    if 'epsilonBeta' in c and (not isinstance(c['epsilonBeta'],(int,float)) or isinstance(c['epsilonBeta'],bool) or not math.isfinite(c['epsilonBeta']) or not math.isclose(c['epsilonBeta'],eb,rel_tol=1e-8,abs_tol=1e-9)):
        return rejected('εβ не согласован с активной шириной проверяемого венца')
    emit('Рабочая ширина проверяемого венца','bвенца=b/2 для шеврона, иначе b',face_width,'мм','табл.5; явная модель двух венцов',f"{n(b)} / {2 if gear_type=='herringbone' else 1}")
    emit('Доля нагрузки проверяемого венца','λ=max(λл;1−λл) для шеврона, иначе1',load_share,page='явная модель распределения нагрузки',substitution=f'λ={n(load_share)}; Tвенца={n(T)}×{n(load_share)}={n(T*load_share)} Н·м')
    emit('Ft проверяемого венца','Ft=2000 T λ/d1',Ft,'Н','табл.6.4',f"2000×{n(T)}×{n(load_share)}/{n(c['d1'])}")
    emit('εα','εα=(√(da1²−db1²)/2+√(da2²−db2²)/2−aw sin αt)/(π mt cos αt)',ea,page='приложение2',substitution=f"(√({n(c['da1'])}²−{n(c['d1']*math.cos(at))}²)/2+√({n(c['da2'])}²−{n(c['d2']*math.cos(at))}²)/2−{n(aw)}×sin({n(c['alphaT'])}°))/(π×{n(m/math.cos(beta))}×cos({n(c['alphaT'])}°))")
    emit('εβ','εβ=bвенца sin β/(π mn)',eb,page='приложение2',substitution=f'{n(face_width)}×sin({n(math.degrees(beta))}°)/(π×{n(m)})')
    emit('εγ','εγ=εα+εβ',eg,page='приложение2',substitution=f'{n(ea)}+{n(eb)}')
    resonance = c['v'] * c['z1'] / 1000
    if resonance >= (1.4 if helical else 1):
        return rejected('Нарушено условие дозарезонансной формулы Kv; необходимо приложение 5 ГОСТ')
    if not (1 <= p.get('accuracy', 7) <= 10):
        return rejected('Некорректная степень точности')
    accuracy = int(p.get('accuracy', 7))
    if accuracy != p.get('accuracy', 7):
        return rejected('Степень точности должна быть целой')
    if accuracy not in range(5, 11):
        return rejected('Таблицы динамической добавки реализованы для степеней точности 5…10')
    col = accuracy - 5
    row = 0 if m <= 3.55 else 1 if m <= 10 else 2
    g0 = ((2.8,3.8,4.7,5.6,7.3,10.), (3.1,4.2,5.3,6.1,8.2,11.), (3.7,4.8,6.4,7.3,10.,13.5))[row][col]
    dynamic_limit = ((85,160,240,380,700,1200), (105,194,310,410,880,1500), (150,250,450,590,1050,1800))[row][col]
    soft = cfg.get('softSurface', True)
    dh = (.02 if soft else .04) if helical else (.06 if soft else .14)
    df = .06 if helical else .16
    wh = min(dynamic_limit, dh * g0 * c['v'] * math.sqrt(aw / c['u']))
    wf = min(dynamic_limit, df * g0 * c['v'] * math.sqrt(aw / c['u']))
    beta_b = math.atan(math.tan(beta) * math.cos(at))
    ze = 190.  # Explicit standard value for steel, Table6.1; not sqrt(.175E) recomputed.
    zh = math.sqrt(2 * math.cos(beta_b) / math.tan(at)) / math.cos(at)
    zeps = math.sqrt(((4 - ea) * (1 - eb) / 3 + eb / ea) if eb < 1 else 1 / ea)
    zv1, zv2 = c['z1'] / math.cos(beta) ** 3, c['z2'] / math.cos(beta) ** 3
    stiffness = 1 / (.05139 + .1425 / zv1 + .1860 / zv2)
    cgamma = stiffness * (.75 * ea + .25)
    a_alpha, y_alpha = cfg.get('aAlpha', 1.), cfg.get('yAlpha', 0.)
    if not .4 <= a_alpha <= 1 or y_alpha < 0:
        return rejected('В этом консервативном профиле требуется 0,4≤aα≤1 и yα≥0')
    khb = cfg.get('KHbeta', p['KHbeta'])
    kfb = cfg.get('KFbeta', p['KFbeta'])
    khv, kfv = 1 + wh * face_width / (Ft * p['KA']), 1 + wf * face_width / (Ft * p['KA'])
    face_auto = None
    if p.get('faceMode') == 'formula':
        if gear_type == 'herringbone':
            return rejected('Автоматическая формула KHβ⁰ не распространяется на шеврон в этой реализации')
        try:
            face_auto = face_factors(width=face_width, diameter=c['d1'], module=m, ea=ea,
                beta=beta, at=at, force=Ft, ka=p['KA'], khv=khv, stiffness=stiffness,
                zeps=zeps, velocity=c['v'], hv=p['faceHV'], deviation=p['faceDeviation'], torque_side=p['torqueSide'])
        except ValueError as error:
            return rejected(str(error))
        khb, kfb = face_auto['KHbeta'], face_auto['KFbeta']
        for label, formula, unit in [
            ('KHbeta0','KHβ⁰=1+0,4 b fkβ⁰ c′ cosαt/(Ft KA KHv Zε²)+Kk(b/d₁)²',''),
            ('KHw','KHw=1−20/((0,01 HV+2)²(v+4)^0,25)',''),
            ('NF','NF=(b/h)²/((b/h)²+b/h+1)',''),
            ('KHbeta','KHβ=1+(KHβ⁰−1)KHw',''), ('KFbeta','KFβ=(KHβ⁰)^NF','')]:
            emit(label,formula,face_auto[label],unit,'табл.6.7–6.7.2; табл.13.4',
                 f"b={n(face_width)}; d₁={n(c['d1'])}; fkβ⁰={n(p['faceDeviation'])} мкм; HV={n(p['faceHV'])}; Kk={n(face_auto['Kk'])}; KHβ⁰={n(face_auto['KHbeta0'])}; KHw={n(face_auto['KHw'])}; NF={n(face_auto['NF'])}")
        assumptions[1] = 'KHβ и KFβ вычислены по полному fkβ⁰, заданному пользователем. Достоверность перекоса и HV требует обоснования.'
    if 'KHbeta0' in cfg and face_auto is None:
        h = 2 * m if helical else 2 * m / ea
        bh = face_width / h
        nf = bh * bh / (bh * bh + bh + 1)
        kfb = cfg['KHbeta0'] ** nf
        emit('h для KFβ','h=2m для косых; 2m/εα для прямых',h,'мм','табл.13.4',f'2×{n(m)}' if helical else f'2×{n(m)}/{n(ea)}')
        emit('NF для KFβ','NF=(b/h)²/((b/h)²+b/h+1)',nf,page='табл.13.4',substitution=f'({n(face_width)}/{n(h)})²/(({n(face_width)}/{n(h)})²+{n(face_width)}/{n(h)}+1)')
        emit('KFβ из KHβ0','KFβ=(KHβ0)^NF',kfb,page='табл.13.4',substitution=f'{n(cfg["KHbeta0"])}^{n(nf)}')
    if khb < 1 or kfb < 1:
        return rejected('Коэффициенты неравномерности по ширине должны быть ≥1')
    fpbe = math.hypot(p['fpb1'], p['fpb2'])
    for title, formula, value, sub, unit, page in [
        ('βb','βb=atan(tan β cos αt)',math.degrees(beta_b),f'atan(tan({n(math.degrees(beta))}°)×cos({n(c["alphaT"])}°))','°','табл.6.2'),
        ('zv1','zv1=z1/cos³β',zv1,f'{c["z1"]}/cos³({n(math.degrees(beta))}°)','','табл.13.6'),
        ('zv2','zv2=z2/cos³β',zv2,f'{c["z2"]}/cos³({n(math.degrees(beta))}°)','','табл.13.6'),
        ('c′','c′=1/(.05139+.1425/zv1+.1860/zv2)',stiffness,f'1/(.05139+.1425/{n(zv1)}+.1860/{n(zv2)})','Н/(мм·мкм)','табл.6.7.1.2'),
        ('cγ','cγ=c′(.75 εα+.25)',cgamma,f'{n(stiffness)}×(.75×{n(ea)}+.25)','Н/(мм·мкм)','табл.6.8.1'),
        ('fpbe','fpbe=√(fpb1²+fpb2²)',fpbe,f'√({n(p["fpb1"])}²+{n(p["fpb2"])}²)','мкм','табл.6.8'),
        ('aα','aα — заданный статистический коэффициент',a_alpha,n(a_alpha),'','табл.6.8; проектное допущение'),
        ('yα','yα — заданная приработка шага',y_alpha,n(y_alpha),'мкм','табл.6.8; проектное допущение'),
        ('g0','g0 — табл.9 по m и точности',g0,f'm={n(m)} мм; степень={accuracy} → {n(g0)}','','табл.9'),
        ('wHv','wHv=min(wlim; δH g0 v √(aw/u))',wh,f'min({dynamic_limit}; {n(dh)}×{n(g0)}×{n(c["v"])}×√({n(aw)}/{n(c["u"])}))','Н/мм','табл.6.6,7'),
        ('wFv','wFv=min(wlim; δF g0 v √(aw/u))',wf,f'min({dynamic_limit}; {n(df)}×{n(g0)}×{n(c["v"])}×√({n(aw)}/{n(c["u"])}))','Н/мм','табл.13.3,7'),
        ('KHβ','KHβ=1+(KHβ⁰−1)KHw' if face_auto else 'KHβ — заданный коэффициент по ширине',khb,n(khb),'','табл.6.7; формула' if face_auto else 'табл.6.7; вход проекта'),
        ('KFβ','KFβ=(KHβ⁰)^NF' if face_auto else 'KFβ — вход или (KHβ0)^NF',kfb,n(kfb),'','табл.13.4; формула' if face_auto else 'табл.13.4; вход проекта'),
    ]:
        emit(title,formula,value,unit,page,sub)
    def tooth_factor(ka, kv, kb, force, bending=False, trace_name=None):
        if not helical:
            if trace_name:
                emit(trace_name,'Kα=1 для прямозубой передачи',1.,page='табл.6.8; табл.13.5',substitution='β=0° → KHα=KFα=1')
            return 1.
        correction = .4 * cgamma * face_width * max(0, a_alpha * fpbe - (0 if bending else y_alpha)) / (force * ka * kv * kb)
        raw = eg / 2 * (.9 + correction) if eg < 2 else .9 + math.sqrt(2 * (eg - 1) / eg) * correction
        upper = eg if bending else eg / (ea * zeps ** 2)
        result = min(upper, max(1., raw))
        if trace_name:
            used_y = 0 if bending else y_alpha
            emit(trace_name+' добавка A','A=.4 cγ b max(0;aα fpbe−yα)/(Ft KA Kv Kβ)',correction,page='табл.6.8',substitution=f'.4×{n(cgamma)}×{n(face_width)}×max(0;{n(a_alpha)}×{n(fpbe)}−{n(used_y)})/({n(force)}×{n(ka)}×{n(kv)}×{n(kb)})')
            branch = f'{n(eg)}/2×(.9+{n(correction)})' if eg < 2 else f'.9+√(2×({n(eg)}−1)/{n(eg)})×{n(correction)}'
            emit(trace_name+' до ограничения','Kα=εγ/2(.9+A) при εγ<2; иначе .9+√(2(εγ−1)/εγ)A',raw,page='табл.6.8',substitution=branch)
            emit(trace_name+' верхняя граница','Kα,max=εγ для изгиба; εγ/(εα Zε²) для контакта',upper,page='табл.6.8; табл.13.5',substitution=n(eg) if bending else f'{n(eg)}/({n(ea)}×{n(zeps)}²)')
            emit(trace_name,'Kα=min(Kα,max;max(1;Kα,raw))',result,page='табл.6.8; табл.13.5',substitution=f'min({n(upper)};max(1;{n(raw)}))')
        return result
    ka = p['KA']
    khv, kfv = 1 + wh * face_width / (Ft * ka), 1 + wf * face_width / (Ft * ka)
    kha, kfa = tooth_factor(ka, khv, khb, Ft, trace_name='KHα'), tooth_factor(ka, kfv, kfb, Ft, True, 'KFα')
    kh, kf = ka * khv * khb * kha, ka * kfv * kfb * kfa
    sigma_h = ze * zh * zeps * math.sqrt(Ft * kh / (face_width * c['d1']) * (c['u'] + 1) / c['u'])
    ybeta = max(.7, 1 - eb * math.degrees(beta) / 120)
    yepsilon = (1 / ea if eb >= 1 else .2 + .8 / ea) if helical else 1.
    yfs = [3.47 + 13.2 / zv1, 3.47 + 13.2 / zv2]
    sigma_f = [Ft / (face_width * m) * kf * yf * ybeta * yepsilon for yf in yfs]
    numeric_subs = {
        'ZE':'190 (сталь, E=210000 МПа, ν=.3)',
        'ZH':f'√(2×cos({n(math.degrees(beta_b))}°)/tan({n(c["alphaT"])}°))/cos({n(c["alphaT"])}°)',
        'Zε':f'√((4−{n(ea)})×(1−{n(eb)})/3+{n(eb)}/{n(ea)})' if eb<1 else f'√(1/{n(ea)}), εβ={n(eb)}≥1',
        'KHv':f'1+{n(wh)}×{n(face_width)}/({n(Ft)}×{n(ka)})',
        'KFv':f'1+{n(wf)}×{n(face_width)}/({n(Ft)}×{n(ka)})',
        'KHα':f'Итог предыдущей ветви: {n(kha)}',
        'KFα':f'Итог предыдущей ветви: {n(kfa)}',
        'Yβ':f'max(.7;1−{n(eb)}×{n(math.degrees(beta))}/120)',
        'Yε':f'1/{n(ea)} при εβ≥1' if helical and eb>=1 else f'.2+.8/{n(ea)} при εβ<1' if helical else '1: β=0°, одна пара зубьев',
    }
    for name, value, formula, page in [
        ('ZE',ze,'ZE=190 для стали E=2,1·10⁵ МПа','табл.6.1, с.15'),
        ('ZH',zh,'ZH=√(2 cos βb / tan αtw) / cos αt','табл.6.2, с.15'),
        ('Zε',zeps,'Zε по εα и εβ','табл.6.3, с.15'),
        ('KHv',khv,'KHv=1+wHv bw/(Ft KA)','табл.6.6, с.16'),
        ('KFv',kfv,'KFv=1+wFv bw/(Ft KA)','табл.13.3, с.30'),
        ('KHα',kha,'KHα по жёсткости, погрешностям и перекрытию','табл.6.8, с.18–19'),
        ('KFα',kfa,'KFα по табл.6.8; для прямых зубьев1','табл.13.5, с.31'),
        ('Yβ',ybeta,'Yβ=max(0,7; 1−εβ β°/120)','табл.13.7, с.32'),
        ('Yε',yepsilon,'Yε=1 для прямых; по εα и εβ для косых','табл.13.8, с.32'),
    ]:
        emit(name, formula, value, page=page, substitution=numeric_subs[name])
    emit('KH','KH=KA KHv KHβ KHα',kh,page='формула33',substitution=f'{n(ka)}×{n(khv)}×{n(khb)}×{n(kha)}')
    emit('KF','KF=KA KFv KFβ KFα',kf,page='формула38',substitution=f'{n(ka)}×{n(kfv)}×{n(kfb)}×{n(kfa)}')
    emit('σH', 'σH=ZE ZH Zε √[Ft KH (u+1)/(bw d₁ u)]', sigma_h, 'МПа', 'формулы31–33, с.14',f'{n(ze)}×{n(zh)}×{n(zeps)}×√({n(Ft)}×{n(kh)}×({n(c["u"])}+1)/({n(face_width)}×{n(c["d1"])}×{n(c["u"])}))')
    hp, fp, hpmax, fpmax, zn, yn = [], [], [], [], [], []
    speed1 = p['speed']
    zv = .85 * c['v'] ** .1 if soft else .925 * c['v'] ** .05
    for i in (1, 2):
        idx = i - 1
        cycles = 60 * speed1 / (1 if i == 1 else c['u']) * p['life']
        neh, nef = cycles * p['muH'], cycles * p['muF']
        nhlim = p[f'NHG{i}'] * 1e6
        zi, yi = contact_life(nhlim, neh), bending_life(nef, 6)
        zn.append(zi); yn.append(yi)
        d = c[f'd{i}']
        if d >= 8400:
            return rejected('Диаметр вне области используемых масштабных зависимостей')
        zx = 1 if d < 700 else math.sqrt(1.07 - 1e-4 * d)
        yx = 1.05 - .000125 * d
        if zx <= 0 or yx <= 0:
            return rejected('Диаметр вне области используемых масштабных зависимостей')
        yz = p['YzLarge'] if c[f'da{i}'] > 270 else p['YzSmall']
        ydelta = 1.082 - .172 * math.log10(m)
        flim = p[f'sigmaF{i}'] * yz * p['YA']
        hp.append(p[f'sigmaH{i}'] / p['SH'] * zi * p['ZR'] * zv * zx)
        fp.append(flim / p['SF'] * yi * ydelta * p['YR'] * yx)
        yield_strength = cfg[f'yield{i}'] if f'yield{i}' in cfg else float(p[f'rowName{i}'].replace('У',''))
        hpmax.append(2.8 * yield_strength)
        # Table18 fallback for steels absent from Table19; this U/U model uses qF=6.
        sy = cfg.get('peakProbabilityFactor', 1.75)
        fpmax.append(flim * 4 * 1.3 / (yz * sy) * yx)
        emit(f'NK{i}','NK=60 n L',cycles,'циклов','приложение3',f'60×{n(speed1/(1 if i==1 else c["u"]))}×{n(p["life"])}')
        emit(f'NHE{i}','NHE=NK μH',neh,'циклов','эквивалентные циклы; μH семинара',f'{n(cycles)}×{n(p["muH"])}')
        emit(f'NFE{i}','NFE=NK μF',nef,'циклов','эквивалентные циклы; μF семинара',f'{n(cycles)}×{n(p["muF"])}')
        emit(f'NHlim{i}','NHlim=NHG·10⁶ из таблицы материала',nhlim,'циклов','вход: Т1 семинара',f'{n(p[f"NHG{i}"])}×10⁶')
        zsub=f'min(2.6;({n(nhlim)}/{n(neh)})^(1/6))' if neh<=nhlim else f'max(.75;({n(nhlim)}/{n(neh)})^(1/20))'
        emit(f'ZN{i}', 'ZN: шестой корень до NHlim; двадцатый после; нижний предел0,75', zi, page='табл.11.3, с.24',substitution=zsub)
        emit(f'YN{i}', 'YN=min(4; max(1; (4·10⁶/NFE)^(1/6)))', yi, page='табл.13.9, с.32–33',substitution=f'min(4;max(1;(4000000/{n(nef)})^(1/6)))')
        emit(f'YFS{i}', 'YFS=3,47+13,2/zv при x=0', yfs[idx], page='табл.13.6, с.31',substitution=f'3.47+13.2/{n([zv1,zv2][idx])}')
        emit(f'Yδ{i}','Yδ=1.082−.172 lg(mn)',ydelta,page='табл.13.12',substitution=f'1.082−.172×lg({n(m)})')
        emit(f'YX{i}','YX=1.05−.000125 d',yx,page='табл.13.14',substitution=f'1.05−.000125×{n(d)}')
        emit(f'ZX{i}','ZX=1 при d<700; иначе √(1.07−.0001d)',zx,page='табл.11.7',substitution=f'd={n(d)}<700 →1' if d<700 else f'√(1.07−.0001×{n(d)})')
        emit(f'YZ{i}','YZ=.9 прокат;1 поковка',yz,page='табл.13.10.3; вход заготовки',substitution=f'da={n(c[f"da{i}"])} мм; граница270 мм → {n(yz)}')
        emit(f'σFlimb{i}','σFlimb=σFlimb0 YZ YA при YT=Yg=Yd=1',flim,'МПа','табл.13.10',f'{n(p[f"sigmaF{i}"])}×{n(yz)}×{n(p["YA"])}')
        emit(f'Zv{i}','Zv=.85 v^.1 для мягкой пары; .925 v^.05 для твёрдой',zv,page='табл.11.5',substitution=f'{.85 if soft else .925}×{n(c["v"])}^{.1 if soft else .05}')
        emit(f'σF{i}', 'σF=Ft KF YFS Yβ Yε/(bw mn)', sigma_f[idx], 'МПа', 'формула37, с.29',f'{n(Ft)}×{n(kf)}×{n(yfs[idx])}×{n(ybeta)}×{n(yepsilon)}/({n(face_width)}×{n(m)})')
        emit(f'σHP{i}', 'σHP=σHlim ZN ZR Zv ZL ZX/SH; ZL=1', hp[idx], 'МПа', 'формула36 и табл.11, с.14,24–25',f'{n(p[f"sigmaH{i}"])}×{n(zi)}×{n(p["ZR"])}×{n(zv)}×1×{n(zx)}/{n(p["SH"])}')
        emit(f'σFP{i}', 'σFP=σFlimb YN Yδ YR YX/SF', fp[idx], 'МПа', 'формула39, с.29; табл.13',f'{n(flim)}×{n(yi)}×{n(ydelta)}×{n(p["YR"])}×{n(yx)}/{n(p["SF"])}')
        emit(f'σHPmax{i}','σHPmax=2.8 σT',hpmax[idx],'МПа','п.3.2.2',f'2.8×{n(yield_strength)}')
        emit(f'σFPmax{i}','σFPmax≈σFlimb·4·1.3·YX/(YZ Sγ)',fpmax[idx],'МПа','табл.18; назначенный Sγ',f'{n(flim)}×4×1.3×{n(yx)}/({n(yz)}×{n(sy)})')
    hp_pair = min(hp) if not helical else min(1.25 * min(hp), max(min(hp), .45 * sum(hp)))
    emit('σHP пары','σHP=min для прямых; clamp(.45(σHP1+σHP2);min;1.25min) для косых',hp_pair,'МПа','с.19',f'min({n(hp[0])};{n(hp[1])})' if not helical else f'min(1.25×{n(min(hp))};max({n(min(hp))};.45×({n(hp[0])}+{n(hp[1])})))')
    startup = p['startup']
    if startup < 1:
        return rejected('Максимальная нагрузка KAS не может быть меньше длительной: KAS≥1')
    peak_ft = Ft * startup
    khv_peak = 1 + wh * face_width / peak_ft
    emit('Ftmax','Ftmax=Ft KAS',peak_ft,'Н','п.3.2.1',f'{n(Ft)}×{n(startup)}')
    emit('KHvmax','KHvmax=1+wHv b/Ftmax',khv_peak,page='табл.6.6',substitution=f'1+{n(wh)}×{n(face_width)}/{n(peak_ft)}')
    kha_peak = tooth_factor(1, khv_peak, khb, peak_ft,trace_name='KHαmax')
    kh_peak = khv_peak * khb * kha_peak
    sigma_h_peak = sigma_h * math.sqrt(startup * kh_peak / kh)
    sigma_f_peak = [value * startup / ka for value in sigma_f]
    emit('KHmax','KHmax=KHvmax KHβ KHαmax, KAmax=1',kh_peak,page='п.3.2.1',substitution=f'{n(khv_peak)}×{n(khb)}×{n(kha_peak)}')
    emit('σHmax', 'σHmax=σH √(Tmax KHmax/(TH KH))', sigma_h_peak, 'МПа', 'п.3.2.1, с.28',f'{n(sigma_h)}×√({n(startup)}×{n(kh_peak)}/{n(kh)})')
    for i in (1, 2):
        emit(f'σFmax{i}', 'σFmax=σF KAS/KA', sigma_f_peak[i-1], 'МПа', 'п.4.2.2, с.52',f'{n(sigma_f[i-1])}×{n(startup)}/{n(ka)}')
    margins = dict(H=hp_pair/sigma_h, F1=fp[0]/sigma_f[0], F2=fp[1]/sigma_f[1],
                   Hmax=min(hpmax)/sigma_h_peak, Fmax1=fpmax[0]/sigma_f_peak[0], Fmax2=fpmax[1]/sigma_f_peak[1])
    for title,key in [('Контактная выносливость','H'),('Изгибная выносливость шестерни','F1'),('Изгибная выносливость колеса','F2'),('Контакт при максимуме','Hmax'),('Изгиб шестерни при максимуме','Fmax1'),('Изгиб колеса при максимуме','Fmax2')]:
        verify(title, margins[key] >= 1, f'Отношение допускаемого к расчётному напряжению: {margins[key]:.4f}; должно быть ≥1. При принятых допущениях.')
    verify('Факторы распределения по ширине', True if cfg.get('faceFactorsConfirmed') else 'pending',
           'KHβ/KFβ вычислены по заданному полному перекосу fkβ⁰ и HV; исходный перекос нужно подтвердить.' if face_auto else 'KHβ/KFβ — входные значения или приближение Т5 семинара. Для уточнения нужны деформации, погрешности направления зуба и монтаж.')
    verify('Условия обработки и смазки', True if cfg.get('surfaceConfirmed') else 'pending',
           'Предполагаются стандартный контур, улучшенная сталь, заданная шероховатость, масло, отсутствие ступеньки шлифования и упрочнения корня.')
    verify('Запас при максимальном изгибе', True if cfg.get('peakProbabilityFactorConfirmed') else 'pending',
           'Для У / У используется приближение табл.18. Sγ=1,75 принят как входное проектное допущение и требует назначения для требуемой вероятности неразрушения.')
    peak_cycles = cfg.get('peakCycles', p.get('peakCount') or None)
    verify('Повторяемость максимальных нагрузок', 'pending' if peak_cycles is None else 0 <= peak_cycles < 1000,
           'Проверка изгиба максимумом по п.4.2.3 предполагает меньше10³ повторений; число пусков должно быть задано.')
    complete = all(x['status'] == 'pass' for x in local_checks)
    return dict(available=True, complete=complete, method='gost-equations-explicit-project-inputs',
                h=sigma_h, fs=sigma_f, hAllow=hp_pair, fAllow=fp,
                marginH=margins['H'], marginF=[margins['F1'], margins['F2']],
                hmax=sigma_h_peak, fsmax=sigma_f_peak, hMaxAllow=min(hpmax), fMaxAllow=fpmax,
                sigmaH=sigma_h, sigmaF=sigma_f, HP=hp_pair, hp=hp, fp=fp,
                sigmaHmax=sigma_h_peak, sigmaFmax=sigma_f_peak, hpmax=hpmax, fpmax=fpmax,
                ZN=zn, YN=yn, YFS=yfs, Ybeta=ybeta, Yepsilon=yepsilon,
                KH=kh, KF=kf, KHv=khv, KFv=kfv, KHalpha=kha, KFalpha=kfa,
                KHbeta=khb, KFbeta=kfb, epsilonBeta=eb, faceWidth=face_width,
                loadShare=load_share, margins=margins, assumptions=assumptions,
                faceAuto=face_auto,
                trace=local_trace, checks=local_checks, source=PDF_URL)
