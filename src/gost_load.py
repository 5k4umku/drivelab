"""Приложения 4 и 6 ГОСТ 21354–87. Коэффициенты внешней и распределённой нагрузки."""
import math

# Таблица 24. Для генератора при КЗ указана только верхняя граница.
START = {'generator':(None,6.),'inductionStart':(2.5,5.),'machineAC':(1.8,4.),
         'machineDC':(1.5,2.2),'winch':(1.5,2.5),'lifting':(1.2,2.),'travel':(1.5,4.),
         'saw':(1.8,2.5),'scraper':(1.5,2.5),'fan':(1.4,1.8),'transmission':(1.4,2.5),
         'electricTransport':(1.6,2.5),'wagonTippler':(1.8,5.),'mill':(1.8,2.2),
         'crusher':(2.,3.5),'crank':(1.8,3.),'rollingMill':(2.5,4.5)}


def scalar(d, key, lo, hi):
    x=d.get(key)
    if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not lo<=x<=hi:
        raise ValueError(f'{key}: задайте конечное число от {lo} до {hi}.')
    return x


def startup_factor(spec, ka):
    if not isinstance(spec,dict) or set(spec)-{'machine','value','softStartReduction','clutchLimit'}:
        raise ValueError('Проверьте поля пускового режима таблицы 24.')
    key=spec.get('machine')
    if not isinstance(key,str) or key not in START:
        raise ValueError('Выберите вид машины из таблицы 24.')
    lo,hi=START[key]
    value=scalar(spec,'value',lo or 1,hi) if 'value' in spec else hi
    reduction=scalar(spec,'softStartReduction',.2,.3) if 'softStartReduction' in spec else 0
    kas=max(ka,value*(1-reduction))
    cap=scalar(spec,'clutchLimit',1,1e4) if 'clutchLimit' in spec else None
    return min(kas,cap) if cap is not None else kas


# Ac, Al, Ab для компоновок на черт. 16. Ноль — одноступенчатая передача.
SCHEMES=((0,0,0),(.024,.2,3.),(-.017,6.,7.5),(.06,1.65,1.3),(0,0,10.6),(.02,8.,9.))


def face_distribution(spec, c, width, force, gear_type, quality):
    required={'span','distance','bearing','torques','scheme','hv'}
    if not isinstance(spec,dict) or set(spec)-required-{'contactGrade'} or not required<=set(spec):
        raise ValueError('Табл. 27 требует span, distance, bearing, torques, scheme и hv.')
    span=scalar(spec,'span',1,100000)
    distance=scalar(spec,'distance',0,span)
    hv=scalar(spec,'hv',1,2000)
    scheme=spec['scheme']
    if type(scheme) is not int or not 0<=scheme<len(SCHEMES):
        raise ValueError('Схема соседней передачи по черт. 16 — целое число от 0 до 5.')
    if spec['torques'] not in ('same','opposite') or spec['bearing'] not in ('plain','roller','ball'):
        raise ValueError('Укажите стороны приложения моментов и тип опор шестерни.')
    grade=spec.get('contactGrade',quality)
    if type(grade) is not int or not 3<=grade<=11:
        raise ValueError('Степень точности по нормам контакта должна быть целой, 3…11.')
    psi=width/c['d1'] * (.5 if gear_type=='herringbone' else 1)
    length=span/width
    position=distance/span
    if not 0 <= position <= 1 or abs(c['beta']) >= 50:
        raise ValueError('Проверьте расположение опор и угол зуба для табл. 27.')
    q_b={'plain':0,'roller':5,'ball':16}[spec['bearing']]
    same=spec['torques']=='same'
    ac,al,ab=SCHEMES[scheme]
    at=12 if same else 8
    psi_offset=.5-position
    ks=.16*psi**3.3*length**2*math.copysign(abs(psi_offset)**.75,psi_offset)
    kb=q_b*psi**.75*(position-.5)/(length+1)**1.5
    kfc=(-1 if same else 1)*ac*psi**3.5*(length-al)**2
    kbc=(-1 if same else 1)*ab*q_b*psi**.7*(length-8)**2*1e-4
    kf=.0375*psi**2*(length+4)
    ea,eb=c['epsilonAlpha'],c['epsilonBeta']
    ze2=(4-ea)*(1-eb)/3+eb/ea if eb<1 else 1/ea
    line=width/ze2
    wm=force/line
    kq=1.6*psi**.33*grade**2/wm
    kw=1-20/((.01*hv+2)**2*(c['v']+4)**.25)
    if not 0 < kw <= 1:
        raise ValueError('Коэффициент приработки вне области табл. 27.')
    ends=[]
    for sign in (1,-1):
        kt=(5+sign*at)*psi**2*(1-.02*abs(c['beta']))*.01
        excess=kt+kf+sign*(ks+kb+kfc+kbc)+kq
        ends.append(dict(KT=kt,Kf=kf,Ks=sign*ks,Kb=sign*kb,Kfc=sign*kfc,Kbc=sign*kbc,KQ=kq,
                         before=1+excess,KHbeta=1+kw*excess))
    initial=max(e['before'] for e in ends)
    if initial<1:
        raise ValueError('Табл. 27 дала KHβ⁰<1. Проверьте исходные данные.')
    height=2*c['m'] if gear_type!='spur' else 2*c['m']/ea
    bh=width*(.5 if gear_type=='herringbone' else 1)/height
    nf=bh*bh/(bh*bh+bh+1)
    return dict(T=ends[0],O=ends[1],KW=kw,wm=wm,KHbeta=max(e['KHbeta'] for e in ends),
                KHbeta0=initial,KFbeta=initial**nf,NF=nf)
