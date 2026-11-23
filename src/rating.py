"""Проверочный расчёт стальной цилиндрической передачи внешнего зацепления.

Напряжения в МПа, силы в Н, момент в Н·м, размеры в мм, скорость в м/с.
Неизвестное допускаемое напряжение и его запас сохраняются как None.
"""
import math
from coefficients import face_factors, REGIMES
from gost_materials import material_properties
from gost_special import helical_allowable, spur_bending
from gost_subsurface import deep_contact, reduced_radius
from gost_root import root_parameters
from gost_geometry import external_geometry, pair_stiffness, tooth_form_factor
from gost_dynamics import MissingDynamicMeasurements, resonance_state, resonant_factor, subcritical_forces
from gost_manufacture import manufacture_factors

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
    if '_flankYA' in p and (not isinstance(p['_flankYA'],list) or len(p['_flankYA'])!=2 or
                             any(not number(y) or not 0<y<=1 for y in p['_flankYA'])):
        return reject('Для реверса задайте два конечных коэффициента 0<YA≤1')
    if '_face27' in p:
        face = p['_face27']
        if (not isinstance(face,dict) or set(face) != {'KHbeta','KFbeta','peakKHbeta'} or
                any(not number(x) or x < 1 for x in face.values())):
            return reject('Таблица 27: нужны конечные KHβ, KFβ и KHβmax не меньше 1')
    if p.get('_tableMissing'):
        return reject('Выбранные модуль, диаметр или скорость выходят за область автоматической Т7. Для отдельного расчёта задайте обоснованные погрешности вручную и отключите Т7; область ГОСТ проверяется независимо.')
    cfg = p.get('gost', {})
    if not isinstance(cfg, dict):
        return reject('gost должен быть объектом JSON')
    positive_p = ('KA','startup','speed','life','muH','muF','ZR','YR','YA','KHbeta','KFbeta')
    if 'materials' not in cfg:
        positive_p += ('SH','SF','YzSmall','YzLarge','sigmaH1','sigmaH2','sigmaF1','sigmaF2','NHG1','NHG2')
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
    flags = {'faceFactorsConfirmed','surfaceConfirmed','peakProbabilityFactorConfirmed','homogeneous','softSurface','oil','herringboneWidthIsTotal','refineContact','refineBending','spurApproximation','tipRelief'}
    numbers = {'aAlpha','aAlphaF','yAlpha','KHbeta','KFbeta','KHbeta0','peakProbabilityFactor','halfLoadShare','yield1','yield2'}
    for key, value in cfg.items():
        if key == 'materials':
            if not isinstance(value, list) or len(value) != 2:
                return reject('gost.materials: нужны два паспорта, сначала шестерня, затем колесо')
        elif key == 'roots':
            if (not isinstance(value, list) or len(value) != 2 or not any(isinstance(v, dict) for v in value)
                    or any(v is not None and not isinstance(v, dict) for v in value)):
                return reject('gost.roots: задайте данные шестерни и колеса, null оставляет базовый Yδ')
        elif key == 'subsurface':
            if not isinstance(value,list) or len(value)!=2 or any(x is not None and not isinstance(x,dict) for x in value):
                return reject('gost.subsurface: укажите два объекта параметров слоя или null')
            if 'materials' not in cfg:
                return reject('Для приложения 8 требуются паспорта обоих материалов')
        elif key == 'dynamics':
            if not isinstance(value, dict):
                return reject('gost.dynamics: требуется объект с данными для приложения 5')
        elif key in ('pitchStatisticH','pitchStatisticF'):
            if not number(value) or value < 0:
                return reject(f'gost.{key}: требуется неотрицательная погрешность в мкм')
        elif key in ('alphaEvidence','runningInMode'):
            if not isinstance(value,str):
                return reject(f'gost.{key}: требуется строка')
        elif key in ('tool1','tool2'):
            if value not in ('standard','protuberance'):
                return reject(f'gost.{key}: выберите standard или protuberance')
        elif key in flags:
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
    if p['KA'] < 1 or p['YA'] > 1 or 'materials' not in cfg and (p['SH'] < 1.1 or p['SF'] < 1.4):
        return reject('Для профиля У: KA≥1, SH≥1.1, SF≥1.4, YA≤1')
    if cfg.get('peakProbabilityFactor',1.75) < 1 or cfg.get('KHbeta0',1) < 1:
        return reject('Sγ и KHβ0 должны быть не меньше1')
    if 'materials' not in cfg and not cfg.get('homogeneous',True):
        return reject('Профиль У / У предполагает однородную структуру материала')
    for i in (1,2):
        if 'materials' not in cfg and f'yield{i}' not in cfg:
            row = p.get(f'rowName{i}')
            if not isinstance(row,str) or not row.startswith('У') or not row[1:].isdigit() or int(row[1:]) <= 0:
                return reject(f'rowName{i}: требуется класс У с числовым пределом текучести')
    if any(c[key] != int(c[key]) for key in ('z1','z2')):
        return reject('Числа зубьев должны быть целыми')
    try:
        return _normative_rating(p,c,b,T,step,check)
    except MissingDynamicMeasurements as exc:
        return dict(reject(str(exc)), reasonCode='missingDynamicMeasurements')
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
    x1 and x2 are normal profile shifts. The basic rack angle is 20 degrees.
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
    if abs(p.get('alpha', 20) - 20) > 1e-9:
        return rejected('Таблица 20 требует исходного контура с углом 20°')
    materials = [material_properties(mat, c['m']) for mat in cfg['materials']] if 'materials' in cfg else []
    if not materials and any(p.get(f'treatment{i}', 'У') != 'У' for i in (1, 2)):
        return rejected('Материальная модель этого профиля ограничена улучшенной сталью У / У')
    if not materials and p.get('mF',6) != 6:
        return rejected('Профиль улучшенной стали У / У использует показатель кривой изгибной усталости qF=6')
    if c['m'] < 1 or c['v'] > 25 or not cfg.get('oil', True):
        return rejected('Область ГОСТ: модуль ≥1 мм, v≤25 м/с, работа со смазкой маслом')
    m, beta, at, ea = c['m'], abs(math.radians(c['beta'])), math.radians(c['alphaT']), c['epsilonAlpha']
    x1, x2 = p.get('x1', 0), p.get('x2', 0)
    geometry = external_geometry(m, c['z1'], c['z2'], c['beta'],
                                 b / 2 if gear_type == 'herringbone' else b,
                                 p['speed'], x1, x2)
    for key in ('alphaT', 'alphaTW', 'aW', 'd1', 'd2', 'da1', 'da2', 'epsilonAlpha', 'u', 'v'):
        if key in c and not math.isclose(c[key], geometry[key], rel_tol=1e-8, abs_tol=1e-9):
            return rejected(f'{key}: значение не согласовано с геометрией по таблице 20')
    atw = math.radians(geometry['alphaTW'])
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
        'Для строк табл. 19 Sγ=1,75 соответствует вероятности неразрушения 0,99 (табл. 18).',
    ]
    if materials:
        assumptions[0] = 'Пределы материала взяты по паспортам: ' + ', '.join(f"{a['label']} (строка {a['row']})" for a in materials)
    if gear_type == 'herringbone':
        share = cfg.get('halfLoadShare', .5)
        if not 0 < share < 1 or not cfg.get('herringboneWidthIsTotal', True):
            return rejected('Для шеврона b — полная активная ширина, 0<доля нагрузки половины<1')
        face_width, load_share = b / 2, max(share, 1 - share)
        assumptions.append('Шеврон моделируется двумя косозубыми венцами; проверяется более нагруженная половина. Это явная расчётная модель распределения нагрузки.')
    Ft = 2000 * T / c['d1'] * load_share
    eb = face_width * math.sin(beta) / (math.pi * m)
    eg = ea + eb
    aw = geometry['aW']
    if 'epsilonBeta' in c and (not isinstance(c['epsilonBeta'],(int,float)) or isinstance(c['epsilonBeta'],bool) or not math.isfinite(c['epsilonBeta']) or not math.isclose(c['epsilonBeta'],eb,rel_tol=1e-8,abs_tol=1e-9)):
        return rejected('εβ не согласован с активной шириной проверяемого венца')
    emit('Рабочая ширина проверяемого венца','bвенца=b/2 для шеврона, иначе b',face_width,'мм','табл.5; явная модель двух венцов',f"{n(b)} / {2 if gear_type=='herringbone' else 1}")
    emit('Доля нагрузки проверяемого венца','λ=max(λл;1−λл) для шеврона, иначе1',load_share,page='явная модель распределения нагрузки',substitution=f'λ={n(load_share)}; Tвенца={n(T)}×{n(load_share)}={n(T*load_share)} Н·м')
    emit('Ft проверяемого венца','Ft=2000 T λ/d1',Ft,'Н','табл.6.4',f"2000×{n(T)}×{n(load_share)}/{n(c['d1'])}")
    emit('αtw','inv αtw=inv αt+2(x₁+x₂) tan 20°/(z₁+z₂)',geometry['alphaTW'],'°','прил. 2, табл. 20, п. 1.2',f"αt={n(c['alphaT'])}°; x₁={n(x1)}; x₂={n(x2)}; z₁+z₂={n(c['z1']+c['z2'])}")
    emit('aw','aw=a cos αt/cos αtw',aw,'мм','прил. 2, табл. 20, п. 1',f"{n(geometry['a'])}×cos({n(c['alphaT'])}°)/cos({n(geometry['alphaTW'])}°)")
    emit('εα','εα=εa₁+εa₂; εaᵢ=zᵢ(tan αaᵢ−tan αtw)/(2π)',ea,page='прил. 2, табл. 20, п. 6',substitution=f"{n(geometry['epsilonA1'])}+{n(geometry['epsilonA2'])}")
    emit('εβ','εβ=bвенца sin β/(π mn)',eb,page='приложение2',substitution=f'{n(face_width)}×sin({n(math.degrees(beta))}°)/(π×{n(m)})')
    emit('εγ','εγ=εα+εβ',eg,page='приложение2',substitution=f'{n(ea)}+{n(eb)}')
    if not (1 <= p.get('accuracy', 7) <= 10):
        return rejected('Некорректная степень точности')
    accuracy = int(p.get('accuracy', 7))
    if accuracy != p.get('accuracy', 7):
        return rejected('Степень точности должна быть целой')
    soft = min(a['hv'] for a in materials) <= 350 if materials else cfg.get('softSurface', True)
    beta_b = math.atan(math.tan(beta) * math.cos(at))
    ze = 190.  # Explicit standard value for steel, Table6.1; not sqrt(.175E) recomputed.
    zh = math.sqrt(2 * math.cos(beta_b) / math.tan(atw)) / math.cos(at)
    zeps = math.sqrt(((4 - ea) * (1 - eb) / 3 + eb / ea) if eb < 1 else 1 / ea)
    zv1, zv2 = c['z1'] / math.cos(beta) ** 3, c['z2'] / math.cos(beta) ** 3
    stiffness = pair_stiffness(zv1, zv2, x1, x2)
    cgamma = stiffness * (.75 * ea + .25)
    manufacture_materials = materials or [dict(sigmaHlim=p[f'sigmaH{i}'],homogeneous=True) for i in (1,2)]
    process = manufacture_factors(cfg,(p['fpb1'],p['fpb2']),c['v'],manufacture_materials,soft)
    a_alpha, a_alpha_f, y_alpha = process['aH'], process['aF'], process['y']
    fpbe = process['fpbe']
    if process['mode']=='table10':
        assumptions[2] = 'Приработка yα рассчитана отдельно по свойствам каждого венца и усреднена по табл. 10.'
        for i, entry in enumerate(process['member'],1):
            limit = 'без ограничения' if entry['cap'] is None else f"предел {n(entry['cap'])} мкм"
            emit(f'yα{i}','yα=min(расчёт по материалу; предел при данной скорости)',entry['y'],'мкм',
                 'табл. 10',f"fpb={n(p[f'fpb{i}'])} мкм; v={n(c['v'])} м/с; σHlim={n(manufacture_materials[i-1]['sigmaHlim'])} МПа; до ограничения {n(entry['raw'])} мкм; {limit}")
    if helical and min(a_alpha,a_alpha_f)<1 and not process['source']:
        verify('Обоснование статистического коэффициента шага','pending',
               'Для назначенного aα<1 укажите статистику изготовления и критерий допустимого повреждения.')
    khb = cfg.get('KHbeta', p['KHbeta'])
    kfb = cfg.get('KFbeta', p['KFbeta'])
    dyn_config = cfg.get('dynamics', {})
    dyn = resonance_state(geometry, stiffness, dyn_config, mesh_width=b)
    zone_names = {'subcritical':'дорезонансная', 'resonant':'резонансная',
                  'transition':'промежуточная', 'supercritical':'закритическая'}
    freq_method = {'estimate':'nE1≈2,4·10⁷ cos αt √[εα cos βb (u²+1+γ)/(1+γ)]/(z₁d₂)',
                   'input':'nE1 по данным проекта',
                   'inertia':'nE1=30/(πz₁)√(10⁶cγb/mпр)'}
    emit('nE1',freq_method[dyn['method']],dyn['nE1'],'об/мин','прил. 5, табл. 25, п. 1',
         f"z₁={c['z1']}; d₂={n(c['d2'])} мм; εα={n(ea)}; b={n(b)} мм; cγ={n(cgamma)}; γ={n(dyn_config.get('attachedRatio',0))}"
         + (f"; mпр={n(dyn['reducedMassKg'])} кг" if dyn['reducedMassKg'] is not None else ''))
    emit('Зона главного резонанса','n₁/nE1',dyn['ratio'],page='прил. 5, табл. 25, п. 2',
         substitution=f"{n(p['speed'])}/{n(dyn['nE1'])} — {zone_names[dyn['zone']]} зона")
    before_resonance = dyn['zone'] == 'subcritical'
    if before_resonance:
        forces = subcritical_forces(m,accuracy,soft,helical,cfg.get('tipRelief',False),
                                    aw,c['u'],c['v'],dyn_config.get('attachedRatio',0))
        wh, wf = forces['wH'], forces['wF']
        khv, kfv = 1 + wh * face_width / (Ft * p['KA']), 1 + wf * face_width / (Ft * p['KA'])
        emit('g0','g0 по модулю и степени точности',forces['g0'],page='табл. 9',substitution=f'm={n(m)} мм; степень {accuracy}')
        for title, delta, value in (('wHv','deltaH',wh), ('wFv','deltaF',wf)):
            emit(title,'w=min(wпред; kм δ g0 v √(aw/u))',value,'Н/мм','табл. 6, 7, 8 и 13',
                 f"min({n(forces['limit'])}; {n(forces['massFactor'])}×{n(forces[delta])}×{n(forces['g0'])}×{n(c['v'])}×√({n(aw)}/{n(c['u'])}))")
    else:
        h_limits = ([a['sigmaHlim'] for a in materials] if materials else [p['sigmaH1'],p['sigmaH2']])
        def load_dynamics(force, ka):
            return resonant_factor(dyn,dyn_config,eg,stiffness,face_width,force,ka,process['yDynamics'],h_limits)
        emit('Приработка шага для динамической нагрузки','yα для fpb из приложения 5',process['yDynamics'],
             'мкм','табл. 25, п. 3.1.1; табл. 10')
        factors = load_dynamics(Ft,p['KA'])
        khv = kfv = factors['Kv']
        if dyn_config.get('coefficients'):
            verify('Внешние коэффициенты динамики для εγ>2','pending',
                   'Проверьте коэффициенты по указанному источнику: '+dyn_config['coefficientSource'])
        for label, formula in (('Bp','Bp=c′(fpb−yα)/(Ft KA/b)'),('Bf','Bf=c′(ff−yα)/(Ft KA/b)'),
                               ('Ca','Ca=(Ca₁+Ca₂)/2'),('BK','BK=1−|c′Ca/(Ft/b)|')):
            emit(label,formula,factors[label],page='прил. 5, табл. 25, п. 3')
        for key, value in factors['Cv'].items():
            emit(key,'Коэффициент для заданного εγ',value,page='ввод проекта' if key in dyn_config.get('coefficients',{}) else 'прил. 5, табл. 26',
                 substitution=f'εγ={n(eg)}; {key}={n(value)}')
        if factors['resonant'] is not None:
            emit('Kv резонансной зоны','Kv=1+Cv1 Bp+Cv2 Bf+Cv4 BK',factors['resonant'],page='прил. 5, табл. 25, п. 3')
        if factors['supercritical'] is not None:
            emit('Kv закритической зоны','Kv=Cv5 Bp+Cv6 Bf+Cv7',factors['supercritical'],page='прил. 5, табл. 25, п. 4')
        if dyn['zone']=='transition':
            emit('Интерполяция Kv','Kv=Kзакр+(Kрез−Kзакр)(1,5−n₁/nE1)/0,35',khv,page='прил. 5, табл. 25, п. 5',
                 substitution=f"{n(factors['supercritical'])}+({n(factors['resonant'])}−{n(factors['supercritical'])})×(1,5−{n(dyn['ratio'])})/0,35")
        dyn['nominal'] = factors
    face_auto = None
    face27 = p.get('_face27')
    if face27:
        khb, kfb = face27['KHbeta'], face27['KFbeta']
        assumptions[1] = 'Распределение нагрузки по ширине задано расчётом приложения 6, табл. 27.'
    elif p.get('faceMode') == 'formula':
        if gear_type == 'herringbone':
            return rejected('Автоматическая формула KHβ⁰ не распространяется на шеврон в этой реализации')
        try:
            face_auto = face_factors(width=face_width, diameter=c['d1'], module=m, ea=ea,
                beta=beta, at=at, force=Ft, ka=p['KA'], khv=khv, stiffness=stiffness,
                zeps=zeps, velocity=c['v'], hv=min(a['hv'] for a in materials) if materials else p['faceHV'], deviation=p['faceDeviation'], torque_side=p['torqueSide'])
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
    if 'KHbeta0' in cfg and face_auto is None and face27 is None:
        h = 2 * m if helical else 2 * m / ea
        bh = face_width / h
        nf = bh * bh / (bh * bh + bh + 1)
        kfb = cfg['KHbeta0'] ** nf
        emit('h для KFβ','h=2m для косых; 2m/εα для прямых',h,'мм','табл.13.4',f'2×{n(m)}' if helical else f'2×{n(m)}/{n(ea)}')
        emit('NF для KFβ','NF=(b/h)²/((b/h)²+b/h+1)',nf,page='табл.13.4',substitution=f'({n(face_width)}/{n(h)})²/(({n(face_width)}/{n(h)})²+{n(face_width)}/{n(h)}+1)')
        emit('KFβ из KHβ0','KFβ=(KHβ0)^NF',kfb,page='табл.13.4',substitution=f'{n(cfg["KHbeta0"])}^{n(nf)}')
    if khb < 1 or kfb < 1:
        return rejected('Коэффициенты неравномерности по ширине должны быть ≥1')
    for title, formula, value, sub, unit, page in [
        ('βb','βb=atan(tan β cos αt)',math.degrees(beta_b),f'atan(tan({n(math.degrees(beta))}°)×cos({n(c["alphaT"])}°))','°','табл.6.2'),
        ('zv1','zv1=z1/cos³β',zv1,f'{c["z1"]}/cos³({n(math.degrees(beta))}°)','','табл.13.6'),
        ('zv2','zv2=z2/cos³β',zv2,f'{c["z2"]}/cos³({n(math.degrees(beta))}°)','','табл.13.6'),
        ('c′','1/c′=0,05139+0,1425/zᵥ₁+0,1860/zᵥ₂−0,01x₁−0,1027x₁/zᵥ₁+0,00455x₂+0,3762x₂/zᵥ₂+0,00734x₁²−0,00054x₂²',stiffness,f'zᵥ₁={n(zv1)}; zᵥ₂={n(zv2)}; x₁={n(x1)}; x₂={n(x2)}','Н/(мм·мкм)','табл. 6, п. 7.1.2'),
        ('cγ','cγ=c′(.75 εα+.25)',cgamma,f'{n(stiffness)}×(.75×{n(ea)}+.25)','Н/(мм·мкм)','табл.6.8.1'),
        ('fpbe','fpbe=√(fpb1²+fpb2²)',fpbe,f'√({n(p["fpb1"])}²+{n(p["fpb2"])}²)','мкм','табл.6.8'),
        ('aα','aα,H≥0,2 для мягкой пары или ≥0,3 для твёрдой',a_alpha,process['sourceH']+' '+process['source'],'','табл. 6, п. 8'),
        ('aα для изгиба','aα,F≥0,4; yα,F=0',a_alpha_f,process['sourceF']+' '+process['source'],'','табл. 13, п. 5'),
        ('yα','yα=(yα₁+yα₂)/2' if process['mode']=='table10' else 'Приработка по заданным данным',y_alpha,
         f"({n(process['member'][0]['y'])}+{n(process['member'][1]['y'])})/2" if process['member'] else n(y_alpha),'мкм','табл. 6, п. 8.2; табл. 10'),
        ('KHβ','KHβ=1+(KHβ⁰−1)KHw' if face_auto else 'KHβ — заданный коэффициент по ширине',khb,n(khb),'','табл.6.7; формула' if face_auto else 'табл.6.7; вход проекта'),
        ('KFβ','KFβ=(KHβ⁰)^NF' if face_auto else 'KFβ — вход или (KHβ0)^NF',kfb,n(kfb),'','табл.13.4; формула' if face_auto else 'табл.13.4; вход проекта'),
    ]:
        emit(title,formula,value,unit,page,sub)
    def tooth_factor(ka, kv, kb, force, bending=False, trace_name=None):
        if face27 and not bending:
            if trace_name:
                emit(trace_name,'KHα=1 для расчётной неравномерности по табл. 27',1.,page='прил. 6, табл. 27, п. 2')
            return 1.
        if not helical:
            if trace_name:
                emit(trace_name,'Kα=1 для прямозубой передачи',1.,page='табл.6.8; табл.13.5',substitution='β=0° → KHα=KFα=1')
            return 1.
        used_alpha = a_alpha_f if bending else a_alpha
        correction = .4 * cgamma * face_width * max(0, used_alpha * fpbe - (0 if bending else y_alpha)) / (force * ka * kv * kb)
        low_overlap = eg < 2 and gear_type != 'herringbone'
        raw = eg / 2 * (.9 + correction) if low_overlap else .9 + math.sqrt(2 * (eg - 1) / eg) * correction
        upper = eg if bending else eg / (ea * zeps ** 2)
        result = min(upper, max(1., raw))
        if trace_name:
            used_y = 0 if bending else y_alpha
            emit(trace_name+' добавка A','A=.4 cγ b max(0;aα fpbe−yα)/(Ft KA Kv Kβ)',correction,page='табл.6.8; табл.13.5',substitution=f'.4×{n(cgamma)}×{n(face_width)}×max(0;{n(used_alpha)}×{n(fpbe)}−{n(used_y)})/({n(force)}×{n(ka)}×{n(kv)}×{n(kb)})')
            branch = f'{n(eg)}/2×(.9+{n(correction)})' if low_overlap else f'.9+√(2×({n(eg)}−1)/{n(eg)})×{n(correction)}'
            emit(trace_name+' до ограничения','Kα=εγ/2(.9+A) при εγ<2; иначе .9+√(2(εγ−1)/εγ)A',raw,page='табл.6.8',substitution=branch)
            emit(trace_name+' верхняя граница','Kα,max=εγ для изгиба; εγ/(εα Zε²) для контакта',upper,page='табл.6.8; табл.13.5',substitution=n(eg) if bending else f'{n(eg)}/({n(ea)}×{n(zeps)}²)')
            emit(trace_name,'Kα=min(Kα,max;max(1;Kα,raw))',result,page='табл.6.8; табл.13.5',substitution=f'min({n(upper)};max(1;{n(raw)}))')
        return result
    ka = p['KA']
    kha, kfa = tooth_factor(ka, khv, khb, Ft, trace_name='KHα'), tooth_factor(ka, kfv, kfb, Ft, True, 'KFα')
    kh, kf = ka * khv * khb * kha, ka * kfv * kfb * kfa
    sigma_h = ze * zh * zeps * math.sqrt(Ft * kh / (face_width * c['d1']) * (c['u'] + 1) / c['u'])
    ybeta = max(.7, 1 - eb * math.degrees(beta) / 120)
    yepsilon = (1 / ea if eb >= 1 else .2 + .8 / ea) if helical else 1.
    tools = [cfg.get(f'tool{i}', 'standard') for i in (1, 2)]
    yfs = [tooth_form_factor(zv, x, tool) for zv, x, tool in zip((zv1, zv2), (x1, x2), tools)]
    sigma_f = [Ft / (face_width * m) * kf * yf * ybeta * yepsilon for yf in yfs]
    numeric_subs = {
        'ZE':'190 (сталь, E=210000 МПа, ν=.3)',
        'ZH':f'√(2×cos({n(math.degrees(beta_b))}°)/tan({n(geometry["alphaTW"])}°))/cos({n(c["alphaT"])}°)',
        'Zε':f'√((4−{n(ea)})×(1−{n(eb)})/3+{n(eb)}/{n(ea)})' if eb<1 else f'√(1/{n(ea)}), εβ={n(eb)}≥1',
        'KHv':f'1+{n(wh)}×{n(face_width)}/({n(Ft)}×{n(ka)})' if before_resonance else f"{zone_names[dyn['zone']]} зона, Kv={n(khv)}",
        'KFv':f'1+{n(wf)}×{n(face_width)}/({n(Ft)}×{n(ka)})' if before_resonance else f"KFv=KHv={n(khv)}",
        'KHα':f'Итог предыдущей ветви: {n(kha)}',
        'KFα':f'Итог предыдущей ветви: {n(kfa)}',
        'Yβ':f'max(.7;1−{n(eb)}×{n(math.degrees(beta))}/120)',
        'Yε':f'1/{n(ea)} при εβ≥1' if helical and eb>=1 else f'.2+.8/{n(ea)} при εβ<1' if helical else '1: β=0°, одна пара зубьев',
    }
    for name, value, formula, page in [
        ('ZE',ze,'ZE=190 для стали E=2,1·10⁵ МПа','табл.6.1, с.15'),
        ('ZH',zh,'ZH=√(2 cos βb / tan αtw) / cos αt','табл.6.2, с.15'),
        ('Zε',zeps,'Zε по εα и εβ','табл.6.3, с.15'),
        ('KHv',khv,'KHv=1+wHv bw/(Ft KA)' if before_resonance else 'KHv=Kv в выбранной зоне','табл. 6, п. 6' if before_resonance else 'прил. 5, табл. 25–26'),
        ('KFv',kfv,'KFv=1+wFv bw/(Ft KA)' if before_resonance else 'KFv=KHv','табл. 13, п. 3' if before_resonance else 'прил. 5, табл. 25–26'),
        ('KHα',kha,'KHα по жёсткости, погрешностям и перекрытию','табл.6.8, с.18–19'),
        ('KFα',kfa,'KFα по табл.6.8; для прямых зубьев1','табл.13.5, с.31'),
        ('Yβ',ybeta,'Yβ=max(0,7; 1−εβ β°/120)','табл.13.7, с.32'),
        ('Yε',yepsilon,'Yε=1 для прямых; по εα и εβ для косых','табл.13.8, с.32'),
    ]:
        emit(name, formula, value, page=page, substitution=numeric_subs[name])
    emit('KH','KH=KA KHv KHβ KHα',kh,page='формула33',substitution=f'{n(ka)}×{n(khv)}×{n(khb)}×{n(kha)}')
    emit('KF','KF=KA KFv KFβ KFα',kf,page='формула38',substitution=f'{n(ka)}×{n(kfv)}×{n(kfb)}×{n(kfa)}')
    emit('σH', 'σH=ZE ZH Zε √[Ft KH (u+1)/(bw d₁ u)]', sigma_h, 'МПа', 'формулы31–33, с.14',f'{n(ze)}×{n(zh)}×{n(zeps)}×√({n(Ft)}×{n(kh)}×({n(c["u"])}+1)/({n(face_width)}×{n(c["d1"])}×{n(c["u"])}))')
    root_data = [None, None]
    hp, fp, hpmax, fpmax, zn, yn = [], [], [], [], [], []
    speed1 = p['speed']
    zr = p['ZR']
    if materials and all(mat['flankRa'] is not None for mat in materials):
        ra = max(mat['flankRa'] for mat in materials)
        if not .63 <= ra <= 2.5:
            return rejected('Шероховатость более грубой поверхности вне приведённых диапазонов Ra табл. 11.4')
        zr = 1. if ra <= 1.25 else .95
    for i in (1, 2):
        idx = i - 1
        if materials:
            mat = materials[idx]
        else:
            hb = (p[f'hb{i}min'] + p[f'hb{i}max']) / 2
            yield_strength = cfg[f'yield{i}'] if f'yield{i}' in cfg else float(p[f'rowName{i}'][1:])
            mat = dict(row='Т1',sigmaHlim=p[f'sigmaH{i}'],sigmaFlimb0=p[f'sigmaF{i}'],
                       NHlim=p[f'NHG{i}']*1e6,homogeneous=True,qF=6,muF=None,SH=p['SH'],SF=p['SF'],
                       YZ=p['YzLarge'] if c[f'da{i}']>270 else p['YzSmall'],YT=1.,Yg=1.,Yd=1.,
                       hpmax=2.8*yield_strength,hPeakFormula='2,8 σт',YgSt=1.,YdSt=1.,
                       staticBase=6.5*hb if 200<=hb<=350 else None,
                       staticSource=f'табл. 19, улучшение: 6,5×{n(hb)} HB; среднее диапазона Т1')
        soft_wheel = mat['hv'] <= 350 if materials else soft
        ya, yr = p.get('_flankYA',[p['YA'],p['YA']])[idx], mat.get('YR') or p['YR']
        if materials and p.get('loadDirection') == 'reversing':
            if mat['gammaA'] is None:
                return rejected(f'Материал {i}: для симметричного реверса требуется обоснованный γA')
            ya = 1 - mat['gammaA']
        if materials and mat['YR'] is None and p.get('autoSurface') and p.get('rootFinish') == 'polished':
            yr = mat['polishedYR']
            if yr is None:
                return rejected(f'Материал {i}: табл. 13.13 требует подтверждения вида полирования и его места в техпроцессе')
        zv = .85 * c['v'] ** .1 if soft_wheel else .925 * c['v'] ** .05
        q = mat['qF']
        mu_f = mat['muF'] if mat['muF'] is not None else p['muF']
        if materials and q and q != p.get('mF',6) and mat['muF'] is None and mu_f != 1:
            regime = str(p.get('loadRegime',''))
            if regime in REGIMES:
                mu_f = REGIMES[regime][2 if q == 9 else 1]
            else:
                return rejected(f'Для материала {i} задайте μF в паспорте для qF={q}')
        cycles = 60 * speed1 / (1 if i == 1 else c['u']) * p['life']
        neh, nef = cycles * p['muH'], cycles * mu_f
        nhlim = mat['NHlim']
        if q is None and (nef < 4e6 or mu_f != 1 and mat['muF'] is None):
            return rejected(f'Материал {i}: для контурной закалки укажите обоснованный испытаниями qF и соответствующий μF')
        zi = contact_life(nhlim, neh, mat['homogeneous'])
        yi = bending_life(nef, q) if q else 1.
        zn.append(zi); yn.append(yi)
        d = c[f'd{i}']
        if d >= 8400:
            return rejected('Диаметр вне области используемых масштабных зависимостей')
        zx = 1 if d < 700 else math.sqrt(1.07 - 1e-4 * d)
        yx = 1.05 - .000125 * d
        if zx <= 0 or yx <= 0:
            return rejected('Диаметр вне области используемых масштабных зависимостей')
        yz = mat['YZ']
        ydelta = 1.082 - .172 * math.log10(m)
        if 'roots' in cfg and cfg['roots'][idx] is not None:
            row = mat['row']
            strength = cfg['materials'][idx].get('yieldStrength') if materials else None
            if not materials and (p.get(f'treatment{i}') != 'У' or not p.get('materialConfirmed')):
                row = 'не подтверждена'
            try:
                root = root_parameters(cfg['roots'][idx], module=m, zv=(zv1,zv2)[idx],
                                       x=(x1,x2)[idx], tool=tools[idx], material_row=row,
                                       yield_strength=strength, spur=gear_type=='spur')
            except ValueError as error:
                return rejected(f'Корень венца {i}: {error}')
            root_data[idx] = root
            ydelta = root['Ydelta']

        flim = mat['sigmaFlimb0'] * mat['YT'] * yz * mat['Yg'] * mat['Yd'] * ya
        hp.append(mat['sigmaHlim'] / mat['SH'] * zi * zr * zv * zx)
        fp.append(flim / mat['SF'] * yi * ydelta * yr * yx)
        hpmax.append(mat['hpmax'])
        sy = cfg.get('peakProbabilityFactor', 1.75)
        fst = mat['staticBase']
        static_factor = mat['YgSt'] * mat['YdSt']
        if mat.get('staticFallback') and q and cfg.get('peakProbabilityFactorConfirmed') and 'peakProbabilityFactor' in cfg:
            fst = flim * (4 * 1.3 if q == 6 else 2.5 * 1.2)
            static_factor = 1.  # Приближение табл. 18 уже учитывает обработку через σFlimb.
            static_source = f'табл. 18, σFSt≈σFlimb YNmax KSt, qF={q}'
        else:
            static_source = mat['staticSource']
        fpmax.append(fst * static_factor * yx / (yz * sy) if fst is not None else None)
        emit(f'NK{i}','NK=60 n L',cycles,'циклов','приложение3',f'60×{n(speed1/(1 if i==1 else c["u"]))}×{n(p["life"])}')
        emit(f'NHE{i}','NHE=NK μH',neh,'циклов','эквивалентные циклы; μH семинара',f'{n(cycles)}×{n(p["muH"])}')
        emit(f'NFE{i}','NFE=NK μF',nef,'циклов','эквивалентные циклы',f'{n(cycles)}×{n(mu_f)}')
        if materials:
            emit(f'NHlim{i}','NHlim=min(30 HB^2,4;120·10⁶)',nhlim,'циклов','табл. 11.3.1',f'min(30×{n(mat["hb"])}^2,4;120·10⁶)')
            emit(f'σHlim{i}',mat['hFormula'],mat['sigmaHlim'],'МПа','табл. 12',f'{mat["label"]}, {mat["evidence"]}')
            emit(f'σFlimb0{i}','Базовый предел изгиба',mat['sigmaFlimb0'],'МПа','табл. '+mat['row'],mat['evidence'])
        else:
            emit(f'NHlim{i}','NHlim=NHG·10⁶ из таблицы материала',nhlim,'циклов','вход: Т1 семинара',f'{n(p[f"NHG{i}"])}×10⁶')
        zsub=f'min({2.6 if mat["homogeneous"] else 1.8};({n(nhlim)}/{n(neh)})^(1/6))' if neh<=nhlim else f'max(.75;({n(nhlim)}/{n(neh)})^(1/20))'
        emit(f'ZN{i}', 'ZN: шестой корень до NHlim; двадцатый после; нижний предел0,75', zi, page='табл.11.3, с.24',substitution=zsub)
        emit(f'YN{i}', 'YN=min(YNmax; max(1; (4·10⁶/NFE)^(1/qF)))', yi, page='табл.13.9, с.32–33',substitution=f'min({4 if q==6 else 2.5};max(1;(4000000/{n(nef)})^(1/{q})))' if q else f'NFE={n(nef)} ≥ 4·10⁶, YN=1')
        yfs_formula = ('YFS=3,47+(13,2−29,7x)/zᵥ+0,092x²' if tools[idx]=='standard'
                       else 'YFS=3,61+0,53x²+(25,3−37,6x)/zᵥ')
        emit(f'YFS{i}', yfs_formula, yfs[idx], page='табл. 13, п. 6, с. 31–32',
             substitution=f"x={n((x1,x2)[idx])}; zᵥ={n((zv1,zv2)[idx])}")
        if root_data[idx]:
            proof = mat.get('evidence') or root['materialEvidence']
            emit(f'Yδ{i}',root['formula'],ydelta,page='табл. 13, п. 12, с. 36',
                 substitution=f"mn={n(m)} мм, ρFn={n(root['radius'])} мм, χ={n(root['gradient'])} мм⁻¹, "
                              f"{root['radiusSource']}, {root['evidence']}. Материал {row}: {proof}")
        else:
            emit(f'Yδ{i}','Yδ=1.082−.172 lg(mn)',ydelta,page='табл.13.12',substitution=f'1.082−.172×lg({n(m)})')
        emit(f'YX{i}','YX=1.05−.000125 d',yx,page='табл.13.14',substitution=f'1.05−.000125×{n(d)}')
        emit(f'ZX{i}','ZX=1 при d<700; иначе √(1.07−.0001d)',zx,page='табл.11.7',substitution=f'd={n(d)}<700 →1' if d<700 else f'√(1.07−.0001×{n(d)})')
        emit(f'YZ{i}','YZ=0,8 для отливки; 0,9 для проката; 1 для поковки и штамповки',yz,page='табл.13.10.3')
        emit(f'σFlimb{i}','σFlimb=σFlimb0 YT YZ Yg Yd YA',flim,'МПа','табл.13.10',f'{n(mat["sigmaFlimb0"])}×{n(mat["YT"])}×{n(yz)}×{n(mat["Yg"])}×{n(mat["Yd"])}×{n(ya)}')
        emit(f'Zv{i}','Zv=0,85 v^0,1 при HV≤350; 0,925 v^0,05 при HV>350',zv,page='табл.11.5',substitution=f'{.85 if soft_wheel else .925}×{n(c["v"])}^{.1 if soft_wheel else .05}')
        emit(f'σF{i}', 'σF=Ft KF YFS Yβ Yε/(bw mn)', sigma_f[idx], 'МПа', 'формула37, с.29',f'{n(Ft)}×{n(kf)}×{n(yfs[idx])}×{n(ybeta)}×{n(yepsilon)}/({n(face_width)}×{n(m)})')
        emit(f'σHP{i}', 'σHP=σHlim ZN ZR Zv ZL ZX/SH; ZL=1', hp[idx], 'МПа', 'формула36 и табл.11, с.14,24–25',f'{n(mat["sigmaHlim"])}×{n(zi)}×{n(zr)}×{n(zv)}×1×{n(zx)}/{n(mat["SH"])}')
        emit(f'σFP{i}', 'σFP=σFlimb YN Yδ YR YX/SF', fp[idx], 'МПа', 'формула39, с.29; табл.13',f'{n(flim)}×{n(yi)}×{n(ydelta)}×{n(yr)}×{n(yx)}/{n(mat["SF"])}')
        if hpmax[idx] is not None:
            emit(f'σHPmax{i}',mat['hPeakFormula'],hpmax[idx],'МПа','п.3.2.2')
        if fpmax[idx] is not None:
            emit(f'σFPmax{i}','σFPmax=σFSt YX/(YZ Sγ)',fpmax[idx],'МПа',static_source,f'{n(fst)}×{n(static_factor)}×{n(yx)}/({n(yz)}×{n(sy)})')
    hp_pair = min(hp) if not helical else min(1.25 * min(hp), max(min(hp), .45 * sum(hp)))
    emit('σHP пары','σHP=min для прямых; clamp(.45(σHP1+σHP2);min;1.25min) для косых',hp_pair,'МПа','с.19',f'min({n(hp[0])};{n(hp[1])})' if not helical else f'min(1.25×{n(min(hp))};max({n(min(hp))};.45×({n(hp[0])}+{n(hp[1])})))')
    shared_geometry = dict(z1=c['z1'], z2=c['z2'], alpha_tw=geometry['alphaTW'],
                           db1=geometry['db1'], db2=geometry['db2'], da1=c['da1'], da2=c['da2'])
    zones = None
    if cfg.get('refineContact'):
        if not helical or not materials:
            return rejected('Приложение 7 требует косозубую или шевронную передачу и паспорта с твёрдостями HB и HV обоих венцов')
        zones = helical_allowable(**shared_geometry, hp1=hp[0], hp2=hp[1],
                                  hb1=materials[0]['hb'], hb2=materials[1]['hb'],
                                  hv1=materials[0]['hv'], hv2=materials[1]['hv'], velocity=c['v'])
        hp_pair = zones['HP']
        emit('σHP по зонам профиля','σHP²=(εα1 δI σHPI²+εα2 δII σHPII²)/εα',hp_pair,'МПа',
             'прил. 7, формула 46, табл. 28',f"σHPI={n(zones['hpI'])}; σHPII={n(zones['hpII'])}; δI={n(zones['deltaI'])}; δII={n(zones['deltaII'])}")
    refine_spur = cfg.get('refineBending') or (not helical and accuracy <= 8 and any(sf > limit for sf, limit in zip(sigma_f, fp)))
    spur_result = None
    if refine_spur:
        if helical or tools[0] != tools[1]:
            return rejected('Приложение 9 требует прямозубую пару и одинаковый тип исходного контура обоих венцов')
        # Табл. 33, 34: стандартная высота ножки 1,25m или 1,4m для особого инструмента.
        hf = 1.25 if tools[0]=='standard' else 1.4
        spur_args = dict(**shared_geometry,x1=x1,x2=x2,module=m,width=face_width,
                         df1=c['d1']-2*m*(hf-x1),df2=c['d2']-2*m*(hf-x2),
                         fpb1=p['fpb1'],fpb2=p['fpb2'],accuracy=accuracy,
                         profile='standard' if tools[0]=='standard' else 'modified',
                         approximation=cfg.get('spurApproximation',False))
        spur_result = spur_bending(**spur_args, force=Ft, ka=ka, khv=khv, khbeta=khb, kfv=kfv, kfbeta=kfb)
        sigma_f = spur_result['sigmaF']
        for i, member in enumerate(('pinion','wheel'), 1):
            item = spur_result[member]
            emit(f'Уточнённое σF{i}','σF=max(σ вершины; σ однопарного контакта)',sigma_f[i-1],
                 'МПа','прил. 9, таблицы 33–34',f"max({n(item['tip'])};{n(item['single'])})")
    startup = p['startup']
    if startup < 1:
        return rejected('Максимальная нагрузка KAS не может быть меньше длительной: KAS≥1')
    peak_ft = Ft * startup
    if before_resonance:
        khv_peak = 1 + wh * face_width / peak_ft
        kfv_peak = 1 + wf * face_width / peak_ft
    else:
        dyn['peak'] = load_dynamics(peak_ft,1.)
        khv_peak = kfv_peak = dyn['peak']['Kv']
    emit('Ftmax','Ftmax=Ft KAS',peak_ft,'Н','п.3.2.1',f'{n(Ft)}×{n(startup)}')
    emit('KHvmax','KHvmax=1+wHv b/Ftmax' if before_resonance else 'Kv при Ftmax, KA=1',khv_peak,
         page='табл. 6, п. 6' if before_resonance else 'прил. 5, табл. 25',
         substitution=f'1+{n(wh)}×{n(face_width)}/{n(peak_ft)}' if before_resonance else f'Ftmax={n(peak_ft)} Н, Kv={n(khv_peak)}')
    khb_peak = face27['peakKHbeta'] if face27 else khb
    kha_peak = tooth_factor(1, khv_peak, khb_peak, peak_ft,trace_name='KHαmax')
    kh_peak = khv_peak * khb_peak * kha_peak
    sigma_h_peak = sigma_h * math.sqrt(startup * kh_peak / kh)
    sigma_f_peak = [value * startup / ka for value in sigma_f]
    if spur_result:
        spur_result['peak'] = spur_bending(**spur_args,force=peak_ft,ka=1.,khv=khv_peak,
                                           khbeta=khb_peak,kfv=kfv_peak,kfbeta=kfb)
        sigma_f_peak = spur_result['peak']['sigmaF']
    emit('KHmax','KHmax=KHvmax KHβmax KHαmax, KAmax=1',kh_peak,page='п.3.2.1',substitution=f'{n(khv_peak)}×{n(khb_peak)}×{n(kha_peak)}')
    emit('σHmax', 'σHmax=σH √(Tmax KHmax/(TH KH))', sigma_h_peak, 'МПа', 'п.3.2.1, с.28',f'{n(sigma_h)}×√({n(startup)}×{n(kh_peak)}/{n(kh)})')
    for i in (1, 2):
        if spur_result:
            item=spur_result['peak']['pinion' if i==1 else 'wheel']
            emit(f'σFmax{i}','σFmax=max(σ вершины; σ однопарного контакта) при Ftmax',sigma_f_peak[i-1],
                 'МПа','п. 4.2.2 и прил. 9',f"max({n(item['tip'])};{n(item['single'])})")
        else:
            emit(f'σFmax{i}', 'σFmax=σF KAS/KA', sigma_f_peak[i-1], 'МПа', 'п.4.2.2, с.52',f'{n(sigma_f[i-1])}×{n(startup)}/{n(ka)}')
    pair_peak_allow = min(hpmax) if None not in hpmax else None
    margins = dict(H=hp_pair/sigma_h, F1=fp[0]/sigma_f[0], F2=fp[1]/sigma_f[1],
                   Hmax=pair_peak_allow/sigma_h_peak if pair_peak_allow is not None else None,
                   Fmax1=fpmax[0]/sigma_f_peak[0] if fpmax[0] is not None else None,
                   Fmax2=fpmax[1]/sigma_f_peak[1] if fpmax[1] is not None else None)
    for title,key in [('Контактная выносливость','H'),('Изгибная выносливость шестерни','F1'),('Изгибная выносливость колеса','F2'),('Контакт при максимуме','Hmax'),('Изгиб шестерни при максимуме','Fmax1'),('Изгиб колеса при максимуме','Fmax2')]:
        if margins[key] is None:
            verify(title, 'pending', 'Для выбранной технологии и твёрдости требуется подтверждённый предел при максимальной нагрузке (п. 3.2.2, табл. 18–19).')
        else:
            verify(title, margins[key] >= 1, f'Отношение допускаемого к расчётному напряжению {margins[key]:.4f}, требуется ≥1.')
    verify('Факторы распределения по ширине', True if cfg.get('faceFactorsConfirmed') else 'pending',
           'KHβ/KFβ вычислены по заданному полному перекосу fkβ⁰ и HV; исходный перекос нужно подтвердить.' if face_auto else 'KHβ/KFβ — входные значения или приближение Т5 семинара. Для уточнения нужны деформации, погрешности направления зуба и монтаж.')
    verify('Условия обработки и смазки', True if cfg.get('surfaceConfirmed') else 'pending',
           'Для проверки требуется подтвердить материал, подготовку переходной поверхности, шероховатость и смазку каждого венца.')
    verify('Запас при максимальном изгибе', True if cfg.get('peakProbabilityFactorConfirmed') else 'pending',
           'В табл. 18 для условий табл. 19 и вероятности неразрушения 0,99 приведён Sγ=1,75. Подтвердите назначение коэффициента.')
    depth_results = [None,None]
    mandatory_pending = None in margins.values()
    allowed_depth_fields = {'core_hv','thickness','profile_confirmed','confirmed_depth',
                            'steel_group','controlled','cycles','safety','peak_safety','boundary_mpa'}
    for i, mat in enumerate(materials):
        params = cfg.get('subsurface',[None,None])[i]
        title = f'Глубинная прочность венца {i+1}'
        if not mat['deepContact']:
            if params is not None:
                return rejected(f'{title}: обработка вне области приложения 8')
            continue
        if params is None:
            verify(title, 'pending', 'Для приложения 8 задайте толщину слоя, твёрдость сердцевины и распределение твёрдости.')
            mandatory_pending = True
            continue
        if set(params) - allowed_depth_fields:
            return rejected(f'{title}: неизвестные параметры слоя {", ".join(sorted(set(params)-allowed_depth_fields))}')
        kind = {'14':'carburized','15':'carbonitrided','16':'nitrided'}[mat['row'][:2]]
        params = dict(params)
        if kind == 'nitrided' and 'cycles' not in params and p.get('loadRegime')=='0':
            params['cycles'] = 60 * speed1 * p['life'] / (1 if i==0 else c['u'])
        try:
            depth = deep_contact(treatment=kind,surface_hv=mat['hv'],rho=reduced_radius(c['d1'],c['u'],c['beta']),
                                 line_load=Ft*kh/face_width,elastic_modulus=210000.,peak_ratio=startup,
                                 sigma_h=sigma_h,sigma_max=sigma_h_peak,**params)
        except (ValueError,TypeError,ArithmeticError) as error:
            verify(title,'pending',f'Приложение 8: {error}')
            mandatory_pending = True
            continue
        depth_results[i] = depth
        criteria = [('fatigue','выносливость')]
        if kind != 'nitrided':
            criteria.append(('peak','максимальная нагрузка'))
        for key, description in criteria:
            item = depth[key]
            passed = item['passed']
            mandatory_pending |= passed is None
            margins[f'Hdepth{i+1}{"max" if key=="peak" else ""}'] = item['margin'] if passed is not None else None
            status = 'pending' if passed is None else passed
            detail = ' '.join(depth['warnings'])
            if item['allowable'] is not None:
                detail = f"σ={n(item['stress'])} МПа, допуск={n(item['allowable'])} МПа. " + detail
                emit(f'{title}, {description}', 'Запас = допускаемое / расчётное напряжение',item['margin'],
                     page='прил. 8, формулы 47, 54',substitution=f"{n(item['allowable'])}/{n(item['stress'])}")
            verify(f'{title}, {description}',status,detail.strip())
    peak_cycles = cfg.get('peakCycles', p.get('peakCount') or None)
    verify('Повторяемость максимальных нагрузок', 'pending' if peak_cycles is None else 0 <= peak_cycles < 1000,
           'Проверка изгиба максимумом по п.4.2.3 предполагает меньше10³ повторений; число пусков должно быть задано.')
    complete = all(x['status'] == 'pass' for x in local_checks)
    return dict(available=True, complete=complete, method='gost-equations-explicit-project-inputs',
                h=sigma_h, fs=sigma_f, hAllow=hp_pair, fAllow=fp,
                marginH=margins['H'], marginF=[margins['F1'], margins['F2']],
                hmax=sigma_h_peak, fsmax=sigma_f_peak, hMaxAllow=pair_peak_allow, fMaxAllow=fpmax,
                sigmaH=sigma_h, sigmaF=sigma_f, HP=hp_pair, hp=hp, fp=fp,
                sigmaHmax=sigma_h_peak, sigmaFmax=sigma_f_peak, hpmax=hpmax, fpmax=fpmax,
                ZN=zn, YN=yn, YFS=yfs, Ybeta=ybeta, Yepsilon=yepsilon,
                KH=kh, KF=kf, KHv=khv, KFv=kfv, KHalpha=kha, KFalpha=kfa,
                KHbeta=khb, KFbeta=kfb, epsilonBeta=eb, faceWidth=face_width,
                loadShare=load_share, margins=margins, assumptions=assumptions,
                **({'roots': root_data} if 'roots' in cfg else {}),
                faceAuto=face_auto, dynamics=dyn, manufacture=process, materialProperties=materials, zonalContact=zones, spurBending=spur_result,
                mandatoryPending=mandatory_pending,subsurface=depth_results,
                trace=local_trace, checks=local_checks, source=PDF_URL)
