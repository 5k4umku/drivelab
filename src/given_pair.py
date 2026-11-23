"""Проверка внешней пары по чертежу и силы в опорах на начальных окружностях."""
import math
from coefficients import prepare
from gost_geometry import external_geometry
from gost_spectrum import stage_rating


def calculate_given(p, rating_inputs):
    p, audit = prepare(p)
    m, b = p['manualModule'], p['manualWidth']
    z1, z2 = p['manualZ1'], p['manualZ2']
    if p['alpha'] != 20 or not (1 <= m <= 50 and 0 < b <= 2000):
        raise ValueError('Табл. 20: исходный контур 20°. По чертежу задайте m=1…50 мм и 0<b≤2000 мм.')
    if any(v != int(v) for v in (z1,z2)) or not 1 <= z1 <= z2 <= 1000:
        raise ValueError('По чертежу нужны целые 1≤z₁≤z₂≤1000.')
    beta = 0 if p['gearType'] == 'spur' else p['manualBeta']
    if p['gearType'] != 'spur' and not 0 < beta <= 35:
        raise ValueError('Для косых зубьев задайте угол 0<β≤35°.')
    chevron = p['gearType'] == 'herringbone'
    c = external_geometry(m, int(z1), int(z2), beta, b/2 if chevron else b, p['speed'], p['x1'], p['x2'])
    cfg = p.get('gost', {})
    if p['materialMode'] == 'custom':
        p['gost'] = {**cfg, 'yield1':p['yield1'], 'yield2':p['yield2']}
    T = 9550 * p['power'] / p['speed']
    # Начальная окружность для статики валов. В расчёте прочности FtH
    # определяется на делительной окружности (прил. 1, табл. 6).
    ft = 2000*T/c['dw1']
    fa = 2000*T/c['d1'] * math.tan(math.radians(beta))
    share = cfg.get('halfLoadShare', .5)
    if isinstance(share, bool) or not isinstance(share,(float,int)) or not 0 < share < 1:
        raise ValueError('Доля нагрузки полушеврона должна лежать между 0 и 1.')
    c.update(aReference=c['a'], a=c['aW'], b=b, Ft=ft, Fr=ft*math.tan(math.radians(c['alphaTW'])),
             Fa=(2*share-1)*fa if chevron else fa, FaHalf=fa/2, FaLeft=share*fa, FaRight=-(1-share)*fa,
             n2=p['speed']/c['u'], T2=T*c['u']*p['efficiency'], betaMin=0,
             error=abs(c['u']-p['ratio']), errorPct=100*abs(c['u']/p['ratio']-1))
    trace = [dict(section='0. Выбор коэффициентов', **item) for item in audit]
    checks = []
    def step(section,title,formula,sub,value,unit='',source='ГОСТ 21354–87, приложение 2, табл. 20'):
        trace.append(dict(section=section,title=title,formula=formula,substitution=sub,value=value,unit=unit,source=source))
    def check(title,ok,detail):
        checks.append(dict(title=title,status=ok if isinstance(ok,str) else 'pass' if ok else 'fail',detail=detail))
    sec='1. Геометрия по чертежу'
    for i in (1,2):
        tooth_depth = 1.4 if cfg.get(f'tool{i}')=='protuberance' else 1.25
        c[f'df{i}'] = c[f'd{i}'] + 2*m*(p[f'x{i}'] - tooth_depth)
        if c[f'df{i}'] <= 0:
            raise ValueError(f'Колесо {i}: неположительный диаметр впадин.')
        step(sec, f'Начальный диаметр dw{i}', 'dw=db/cos αtw', f"db={c[f'db{i}']:.7g}; αtw={c['alphaTW']:.7g}°", c[f'dw{i}'], 'мм')
        step(sec, f'Толщина зуба на окружности вершин {i}', 'sa=da[(π/2+2x tan αn)/z + inv αt − inv αa]',
             f"x={p[f'x{i}']}; z={c[f'z{i}']}; da={c[f'da{i}']:.7g}",c[f'tipThickness{i}'],'мм','Геометрия эвольвенты исходной рейки')
        check(f'Предварительная проверка подрезания, колесо {i}', p[f'x{i}'] >= 1 - c[f'zv{i}']*math.sin(math.radians(20))**2/2,
              f"Для рейки с ha*=1 проверено x ≥ 1 − zv sin²αn/2; x={p[f'x{i}']}, zv={c[f'zv{i}']:.7g}.")
    step(sec,'Рабочее межосевое расстояние','aw = (dw₁ + dw₂)/2',f"({c['dw1']:.7g} + {c['dw2']:.7g})/2",c['a'],'мм')
    step(sec,'Торцовое перекрытие','εα = εα1 + εα2',f"{c['epsilonA1']:.7g} + {c['epsilonA2']:.7g}",c['epsilonAlpha'])
    step(sec,'Окружная сила на начальной окружности','Ftw=2000T₁/dw₁',f"2000 × {T:.7g} / {c['dw1']:.7g}",ft,'Н','Равновесие вала')
    check('Передаточное число',c['errorPct']<=p['ratioTolerance'],f"uф={c['u']:.6g}; целевое u={p['ratio']}; отклонение {c['errorPct']:.5g} %.")
    rating = stage_rating(rating_inputs(p,c),c,b,T,step,check)
    c.update(contactMargin=rating.get('marginH'), bendingMargin=min(rating['marginF']) if rating.get('marginF') and None not in rating['marginF'] else None)
    status = 'fail' if any(x['status']=='fail' for x in checks) else 'pending' if any(x['status']=='pending' for x in checks) else 'pass'
    return dict(errors=[],input=p,trace=trace,checks=checks,status=status,variants=[c],chosen=c,recommended=None,T=T,
                hp=rating.get('hp',[]),fp=rating.get('fp',[]),HP=rating.get('hAllow'),FP=min(rating['fp']) if rating.get('fp') and None not in rating['fp'] else None,
                psi=b/c['a'],ap=None,ac=None,a=c['a'],b=b,mmin=m,mmax=m,sizeComparison=[],rating=rating,coefficientAudit=audit)
