"""Deterministic helical gear design. Standard-library-only, CPython 3.11+.

mm / N / N·m / MPa / kW / rpm / hours. Public API: calculate(dict) -> dict.
The seminar profile is deliberately explicit; provenance travels with every step.
"""
import json
import math
from pathlib import Path
from rating import normative_rating

VERSION = '0.2.0'
DEFAULTS = json.loads(Path(__file__).with_name('defaults.json').read_text(encoding='utf-8'))
TABLES = json.loads(Path(__file__).with_name('seminar_tables.json').read_text(encoding='utf-8'))
MATERIALS = [
    ('У345',174,217,460,345,970,1270,10), ('У395',187,229,480,360,1100,1350,11),
    ('У440',197,235,500,380,1230,1400,12), ('У490',212,248,530,400,1370,1490,14),
    ('У540',223,262,550,420,1510,1570,16), ('У590',235,277,580,450,1650,1660,18),
    ('У640',248,293,610,470,1790,1750,21), ('У685',262,311,640,500,1920,1860,24),
    ('У735',277,321,670,520,2060,1940,26), ('У785',293,331,690,550,2200,2020,29),
]

def f(x, digits=6):
    return f'{x:.{digits}f}'.rstrip('0').rstrip('.').replace('.', ',') if isinstance(x,(float,int)) else str(x)

def r10(x):
    base = 10 ** math.floor(math.log10(x))
    return next(v*base for v in [1,1.25,1.6,2,2.5,3.15,4,5,6.3,8,10] if v*base >= x-1e-10)

def table_fpb(module, diameter, grade=7):
    table=TABLES['T7']
    group=next((i for i,(lo,hi) in enumerate(table['moduleGroupsMm']) if lo<=module<=hi),None)
    column=next((i for i,upper in enumerate(table['diameterUpperBoundsMm']) if diameter<=upper),None)
    if group is None or column is None: return None
    return table['grades'][str(grade)]['fpb'][group][column]

def rating_inputs(p,c):
    out=dict(p)
    if p.get('autoTables',True):
        for i in (1,2):
            val=table_fpb(c['m'],c[f'd{i}'])
            if val is not None: out[f'fpb{i}']=val
    return out

def material_pair(p):
    """Keep pinion's class, select wheel exactly two softer classes from T1."""
    index = int(p['row1'])
    if not 2 <= index < len(MATERIALS):
        raise ValueError('Для правила двух строк класс шестерни должен быть не ниже У440')
    p = dict(p)
    for i, row in [(1,index),(2,index-2)]:
        name,lo,hi,h,ff,hmax,fmax,nhg = MATERIALS[row]
        for key,value in {'row':row,'rowName':name,'hb':None,'sigmaH':h,'sigmaF':ff,'NHG':nhg,'sigmaHmax':hmax,'sigmaFmax':fmax}.items():
            if key!='hb': p[key+str(i)] = value
        p[f'hb{i}min'], p[f'hb{i}max'] = lo,hi
    p['materialSource']=f"Т1 семинара; шестерня {p['rowName1']}, колесо {p['rowName2']} на две строки мягче по правилу пользователя"
    return p

def validate(p):
    errors=[]
    unknown=set(p)-set(DEFAULTS)-{'gost'}
    if unknown:
        return ['Неподдерживаемые параметры проекта: '+', '.join(sorted(map(str,unknown)))]
    for key,default in DEFAULTS.items():
        value=p.get(key)
        if isinstance(default,bool):
            if not isinstance(value,bool): errors.append(f'{key}: требуется логическое значение')
        elif isinstance(default,(int,float)):
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
                errors.append(f'{key}: требуется конечное неотрицательное число')
        elif not isinstance(value,str) or len(value)>1000: errors.append(f'{key}: некорректный текст')
    if errors: return errors
    if p['gearType'] not in ('spur','helical','herringbone'): errors.append('Неизвестный тип передачи')
    positive=['power','speed','ratio','efficiency','life','KA','startup','psiBd','KHbeta','KFbeta','muH','muF','mH','mF','NFG','SH','SF','sigmaH1','sigmaH2','sigmaF1','sigmaF2','NHG1','NHG2','ZR','ZVZL','YR','YA','YzSmall','YzLarge']
    errors += [f'{key}: должно быть больше нуля' for key in positive if p[key]<=0]
    if not 1<p['ratio']<=20: errors.append('Передаточное число: 1 < u ≤ 20')
    if p['efficiency']>1: errors.append('КПД не может превышать 1')
    if not 15<=p['alpha']<=30 or not 0<p['betaMax']<=35: errors.append('Углы: αn = 15…30°, 0 < βmax ≤ 35°')
    if p['power']>10000 or p['speed']>100000 or p['life']>1e7: errors.append('Исходные данные за диапазоном учебного расчёта')
    if p['psiBd']>2 or p['aOverride']>10000: errors.append('Проверьте ширину и межосевое расстояние')
    for i in (1,2):
        if p[f'hb{i}min']>p[f'hb{i}max']: errors.append('Минимальная твёрдость выше максимальной')
        if p[f'row{i}']!=int(p[f'row{i}']): errors.append('Номер позиции таблицы должен быть целым')
    try:
        modules=[float(x.replace(',','.')) for x in p['modules'].replace(';',' ').split()]
        if not 1<=len(modules)<=30 or any(not math.isfinite(x) or not .1<=x<=50 for x in modules): raise ValueError()
    except ValueError: errors.append('Модули: 1…30 чисел от 0,1 до 50 мм через пробел')
    return errors

def calculate(p, compare=False):
    if not isinstance(p,dict): return dict(errors=['Исходные данные должны быть объектом JSON'],trace=[],checks=[],variants=[])
    p={**DEFAULTS,**p}
    errors=validate(p)
    if errors: return dict(errors=errors,trace=[],checks=[],variants=[])
    trace,checks=[],[]
    def step(section,title,formula,sub,value,unit='',source='Семинары: бланк и таблицы Т1–Т9'):
        trace.append(dict(section=section,title=title,formula=formula,substitution=sub,value=value,unit=unit,source=source))
        return value
    def check(title,ok,detail):
        checks.append(dict(title=title,status=ok if isinstance(ok,str) else 'pass' if ok else 'fail',detail=detail))
    u=p['ratio']; speed=p['speed']; ka=p['KA']
    kind=p['gearType']; spur=kind=='spur'; chevron=kind=='herringbone'
    design_ka=490 if spur else 430; design_km=4 if spur else 2.5
    if p.get('autoTables',True):
        dynamic=TABLES['T6']['spur_unmodified' if spur else 'helical']
        p['deltaH'],p['deltaF']=dynamic['deltaH_soft'],dynamic['deltaF']
    sec='1. Кинематика и нагрузка'
    T=step(sec,'Момент шестерни','T₁ = 9550 P₁ / n₁',f"9550 × {f(p['power'])} / {f(speed)}",9550*p['power']/speed,'Н·м')
    step(sec,'Частота вращения колеса','n₂ = n₁ / u',f'{f(speed)} / {f(u)}',speed/u,'мин⁻¹')
    step(sec,'Мощность на колесе','P₂ = P₁ η',f"{f(p['power'])} × {f(p['efficiency'])}",p['power']*p['efficiency'],'кВт')
    step(sec,'Момент колеса при заданном u','T₂ = T₁ u η',f"{f(T)} × {f(u)} × {f(p['efficiency'])}",T*u*p['efficiency'],'Н·м')
    hp,fp=[],[]
    sec='2. Материалы и долговечность'
    for i in (1,2):
        Ni=step(sec,f'Число циклов NК{i}','NК = 60 n L / 10⁶',f"60 × {f(speed/(1 if i==1 else u))} × {f(p['life'])} / 10⁶",60*speed*p['life']/(1 if i==1 else u)/1e6,'млн')
        zn=min(2.6,max(1,(p['NHG'+str(i)]/(Ni*p['muH']))**(1/p['mH'])))
        yn=min(4,max(1,(p['NFG']/(Ni*p['muF']))**(1/p['mF'])))
        step(sec,f'Контактная долговечность ZN{i}','ZN = ограничить((NHG/(NК μH))^(1/mH); 1; 2,6)',f"({f(p['NHG'+str(i)])}/({f(Ni)} × {f(p['muH'])}))^(1/{p['mH']})",zn,source='Т2: диапазон для У и ОЗ')
        step(sec,f'Долговечность при изгибе YN{i}','YN = ограничить((NFG/(NК μF))^(1/mF); 1; 4)',f"({f(p['NFG'])}/({f(Ni)} × {f(p['muF'])}))^(1/{p['mF']})",yn,source='Т2: диапазон для У и ОЗ')
        h=p['sigmaH'+str(i)]*zn*p['ZR']*p['ZVZL']/p['SH']
        ff=p['sigmaF'+str(i)]*yn*p['YR']*p['YA']*p['YzSmall']/p['SF']
        hp.append(step(sec,f'Допускаемое контактное напряжение σHP{i}','σHP = σHlim ZN ZR (ZV ZL) / SH',f"{f(p['sigmaH'+str(i)])} × {f(zn)} × {f(p['ZR'])} × {f(p['ZVZL'])} / {f(p['SH'])}",h,'МПа','Т1, Т2, Т3'))
        fp.append(step(sec,f'Предварительное допускаемое изгибное напряжение σFP{i}','σFP = σFlim YN YR YA Yz / SF',f"{f(p['sigmaF'+str(i)])} × {f(yn)} × {f(p['YR'])} × {f(p['YA'])} × {f(p['YzSmall'])} / {f(p['SF'])}",ff,'МПа','Т1, Т2, Т3; до выбора заготовки'))
    zw=step(sec,'Коэффициент приработки','ZW = ограничить(0,45 (1 + max(σHP)/min(σHP)); 1; 1,25)',f'0,45 × (1 + {f(max(hp))}/{f(min(hp))})',min(1.25,max(1,.45*(1+max(hp)/min(hp)))))
    HP=step(sec,'Допускаемое контактное напряжение пары','σHP = ZW min(σHP₁; σHP₂)',f'{f(zw)} × {f(min(hp))}',zw*min(hp),'МПа')
    FP=min(fp)
    sec='3. Проектировочный расчёт'
    psi=step(sec,'Коэффициент ширины','ψba = 2 ψbd / (u + 1)',f"2 × {f(p['psiBd'])} / {f(u+1)}",2*p['psiBd']/(u+1))
    ap=step(sec,'Предварительное межосевое расстояние',f'a′ = {design_ka} (u + 1) ∛(KA KHβ T₁ / (ψba u σHP²))',f"{design_ka} × {f(u+1)} × ∛({f(ka)} × {f(p['KHbeta'])} × {f(T)} / ({f(psi)} × {f(u)} × {f(HP)}²))",design_ka*(u+1)*(ka*p['KHbeta']*T/(psi*u*HP**2))**(1/3),'мм')
    b0=psi*ap; d0=2*ap/(u+1); f0=2000*T/d0; v0=math.pi*d0*speed/60000
    for title,formula,sub,value,unit in [
        ('Предварительная ширина','b′ = ψba a′',f'{f(psi)} × {f(ap)}',b0,'мм'),
        ('Предварительный диаметр шестерни','d′₁ = 2 a′ / (u + 1)',f'2 × {f(ap)} / {f(u+1)}',d0,'мм'),
        ('Предварительная окружная сила','F′t = 2000 T₁ / d′₁',f'2000 × {f(T)} / {f(d0)}',f0,'Н'),
        ('Предварительная окружная скорость','v′ = π d′₁ n₁ / 60000',f'π × {f(d0)} × {f(speed)} / 60000',v0,'м/с')]: step(sec,title,formula,sub,value,unit)
    khv=1+p['deltaH']*p['g0']*v0*b0*math.sqrt(ap/u)/(ka*p['KHbeta']*f0)
    kfv=1+p['deltaF']*p['g0']*v0*b0*math.sqrt(ap/u)/(ka*p['KFbeta']*f0)
    kha=1 if spur else .9+1.7*b0*math.hypot(p['fpb1'],p['fpb2'])/(ka*p['KHbeta']*khv*f0)
    kfa=1 if spur else min(1.6,max(1,kha))
    for label,value,delta,kb in [('KHv',khv,p['deltaH'],p['KHbeta']),('KFv',kfv,p['deltaF'],p['KFbeta'])]:
        step(sec,f'Динамический коэффициент {label}','Kv = 1 + δ g₀ v′ b′ √(a′/u) / (KA Kβ F′t)',f"1 + {f(delta)} × {f(p['g0'])} × {f(v0)} × {f(b0)} × √({f(ap)}/{f(u)}) / ({f(ka)} × {f(kb)} × {f(f0)})",value,source='Т6, Т7: предварительная геометрия')
    step(sec,'Распределение нагрузки между зубьями','KHα = 1 для прямозубой передачи' if spur else 'KHα = 0,9 + 1,7 b′ √(fpb₁² + fpb₂²) / (KA KHβ KHv F′t)','1' if spur else f"0,9 + 1,7 × {f(b0)} × √({f(p['fpb1'])}² + {f(p['fpb2'])}²) / ({f(ka)} × {f(p['KHbeta'])} × {f(khv)} × {f(f0)})",kha,source='Бланк, Т7; fpb в мкм по эмпирической формуле')
    step(sec,'Ограничение KFα по бланку','KFα = ограничить(KHα; 1; 1,6)',f'ограничить({f(kha)}; 1; 1,6)',kfa,source='Семинар, диапазон KFα = 1…1,6; округление не применяется')
    ac=step(sec,'Уточнение межосевого расстояния','aрасч = a′ ∛(KHv KHα)',f'{f(ap)} × ∛({f(khv)} × {f(kha)})',ap*(khv*kha)**(1/3),'мм')
    a=p['aOverride'] or r10(ac); b=psi*a; dw=2*a/(u+1); ft=2000*T/dw
    step(sec,'Принятое межосевое расстояние','aw = выбор из ряда R10 вверх' if not p['aOverride'] else 'aw задано пользователем',f'{f(ac)} → {f(a)}',a,'мм','Т8; изменение aw требует пересчёта')
    step(sec,'Рабочая ширина','bw = ψba aw',f'{f(psi)} × {f(a)}',b,'мм')
    sec='4. Выбор модуля и зубьев'
    mmin=step(sec,'Минимальный нормальный модуль',f'mn,min = {design_km} KA KFβ KFv KFα Ft / (bw min(σFP))',f"{f(design_km)} × {f(ka)} × {f(p['KFbeta'])} × {f(kfv)} × {f(kfa)} × {f(ft)} / ({f(b)} × {f(FP)})",design_km*ka*p['KFbeta']*kfv*kfa*ft/(b*FP),'мм')
    mmax=step(sec,'Максимальный нормальный модуль','mn,max = dw₁ / 17',f'{f(dw)} / 17',dw/17,'мм')
    inrange=sorted(set(float(x.replace(',','.')) for x in p['modules'].replace(';',' ').split()))
    inrange=[m for m in inrange if mmin<=m<=mmax]
    modules=inrange[1:-1] if p['excludeEdges'] and len(inrange)>4 else inrange
    variants=[]
    for m in modules:
        sine=math.pi*m/(b/2 if chevron else b)
        if sine>=1: continue
        bmin=math.asin(sine); lo=2*a/m*math.cos(math.radians(p['betaMax'])); hi=2*a/m*math.cos(bmin)
        if spur:
            bmin=0
            lo=math.ceil(2*ac/m); hi=math.ceil(2*a/m)+2
            if p['aOverride']:
                lo=hi=2*a/m
                if abs(lo-round(lo))>1e-9: continue
        if lo>hi or hi>100000: continue
        candidates=[]
        for zs in range(math.ceil(lo),math.floor(hi)+1):
            z1=math.floor(zs/(u+1)+.5); z2=zs-z1
            if z1>0 and math.gcd(z1,z2)==1: candidates.append((abs(z2/z1-u),zs,z1,z2))
        if not candidates: continue
        error,zs,z1,z2=min(candidates)
        actual_a=m*zs/2 if spur else a
        beta=0 if spur else math.acos(m*zs/(2*a)); at=math.atan(math.tan(math.radians(p['alpha']))/math.cos(beta))
        d1=m*z1/math.cos(beta); d2=m*z2/math.cos(beta)
        da1=d1+2*m; da2=d2+2*m; db1=d1*math.cos(at); db2=d2*math.cos(at)
        ea=(math.sqrt((da1/2)**2-(db1/2)**2)+math.sqrt((da2/2)**2-(db2/2)**2)-actual_a*math.sin(at))/(math.pi*m/math.cos(beta)*math.cos(at))
        Ft=2000*T/d1
        variants.append(dict(m=m,z1=z1,z2=z2,error=error,a=actual_a,b=b,beta=math.degrees(beta),betaMin=math.degrees(bmin),alphaT=math.degrees(at),lo=lo,hi=hi,u=z2/z1,errorPct=error/u*100,d1=d1,d2=d2,da1=da1,da2=da2,df1=d1-2.5*m,df2=d2-2.5*m,db1=db1,db2=db2,Ft=Ft,Fr=Ft*math.tan(at),Fa=0 if chevron else Ft*math.tan(beta),FaHalf=Ft*math.tan(beta)/2 if chevron else 0,v=math.pi*d1*speed/60000,n2=speed*z1/z2,T2=T*z2/z1*p['efficiency'],epsilonAlpha=ea,epsilonBeta=(b/2 if chevron else b)*math.sin(beta)/(math.pi*m),zv1=z1/math.cos(beta)**3,zv2=z2/math.cos(beta)**3))
        if chevron:
            cfg=p.get('gost') if isinstance(p.get('gost'),dict) else {}
            share=cfg.get('halfLoadShare',.5)
            if isinstance(share,(int,float)) and not isinstance(share,bool) and math.isfinite(share) and 0<share<1:
                variants[-1].update(Fa=(2*share-1)*Ft*math.tan(beta),FaLeft=share*Ft*math.tan(beta),FaRight=-(1-share)*Ft*math.tan(beta))
    recommended=min(variants,key=lambda c:(c['error'],c['m'])) if variants else None
    chosen=next((c for c in variants if c['m']==p['selectedModule']),recommended)
    for variant in variants:
        trial=normative_rating(rating_inputs(p,variant),variant,b,T)
        variant['contactMargin']=trial.get('marginH')
        variant['bendingMargin']=min(trial['marginF']) if trial.get('marginF') else None
    check('Твёрдость шестерни выше твёрдости колеса',p['hb1min']>p['hb2min'] and p['hb1max']>p['hb2max'],f"Шестерня {p['hb1min']}–{p['hb1max']} HB; колесо {p['hb2min']}–{p['hb2max']} HB. Сравниваются заданные диапазоны; они могут пересекаться.")
    if p['treatment1']==p['treatment2']=='У': check('Колесо на две строки мягче при У / У',p['row1']==p['row2']+2,f"Класс шестерни {p['rowName1']}; колеса {p['rowName2']}. Правило пользователя, 29.10.2026.")
    check('Строки материалов',True if p['materialConfirmed'] else 'pending',p['materialSource'])
    check('Диапазоны коэффициентов',1<=khv<=2 and 1<=kfv<=2 and 1<=kha<=2 and 1<=kfa<=1.6,f'KHv = {f(khv)}, KFv = {f(kfv)}, KHα = {f(kha)}, KFα = {f(kfa)}. Ограничение KFα показано отдельным шагом.')
    check('Межосевое расстояние',a>=ac,f'aw = {f(a)} мм ≥ aрасч = {f(ac)} мм')
    check('Доступны варианты',bool(variants),f"Модули в интервале {f(mmin)}…{f(mmax)} мм: {'; '.join(map(f,inrange))}. При >4 модулях исключаются крайние, если включено правило семинара.")
    rating=None
    if chosen:
        c=chosen
        a=c['a']
        if spur:
            step(sec,'Коррекция межосевого расстояния прямозубой пары','aw = mn (z₁ + z₂) / 2',f"{f(c['m'])} × {c['z1']+c['z2']} / 2",a,'мм','x₁ = x₂ = 0; геометрическое замыкание после выбора зубьев')
            check('Межосевое расстояние окончательной пары',a>=ac,f'aw = {f(a)} мм ≥ aрасч = {f(ac)} мм')
        for title,formula,sub,value,unit in [
            ('Минимальный угол наклона','β = 0 для прямых зубьев' if spur else 'βmin = arcsin(π mn / bактив)','0' if spur else f"arcsin(π × {f(c['m'])} / {f(b/2 if chevron else b)})",c['betaMin'],'°'),
            ('Минимальная сумма зубьев',('zΣ = 2 aw / mn' if p['aOverride'] else 'zΣ,min = ceil(2 aрасч / mn)') if spur else 'zΣ,min = 2 aw cos βmax / mn',(f"2 × {f(a)} / {f(c['m'])}" if p['aOverride'] else f"ceil(2 × {f(ac)} / {f(c['m'])})") if spur else f"2 × {f(a)} × cos {f(p['betaMax'])}° / {f(c['m'])}",c['lo'],''),
            ('Максимальная сумма зубьев',('zΣ = 2 aw / mn' if p['aOverride'] else 'zΣ,max = ceil(2 aR10 / mn) + 2') if spur else 'zΣ,max = 2 aw cos βmin / mn',(f"2 × {f(a)} / {f(c['m'])}" if p['aOverride'] else f"ceil(2 × {f(r10(ac))} / {f(c['m'])}) + 2") if spur else f"2 × {f(a)} × cos {f(c['betaMin'])}° / {f(c['m'])}",c['hi'],''),
            ('Выбор зубьев шестерни','z₁ = round(zΣ / (u + 1))',f"round({c['z1']+c['z2']} / {f(u+1)})",c['z1'],''),
            ('Выбор зубьев колеса','z₂ = zΣ − z₁',f"{c['z1']+c['z2']} − {c['z1']}",c['z2'],''),
            ('Фактическое передаточное число','uф = z₂ / z₁',f"{c['z2']} / {c['z1']}",c['u'],''),
            ('Отклонение передаточного числа','δu = |uф − u| / u × 100%',f"|{f(c['u'])} − {f(u)}| / {f(u)} × 100",c['errorPct'],'%')]: step(sec,title,formula,sub,value,unit)
        sec='5. Геометрия и силы'
        step(sec,'Угол наклона зубьев','β = arccos(mn (z₁ + z₂) / (2 aw))',f"arccos({f(c['m'])} × {c['z1']+c['z2']} / (2 × {f(a)}))",c['beta'],'°')
        step(sec,'Торцовый угол профиля','αt = arctan(tan αn / cos β)',f"arctan(tan {f(p['alpha'])}° / cos {f(c['beta'])}°)",c['alphaT'],'°')
        for i in (1,2):
            key=str(i); d=c['d'+key]
            step(sec,f'Делительный диаметр d{i}','d = mn z / cos β',f"{f(c['m'])} × {c['z'+key]} / cos {f(c['beta'])}°",d,'мм')
            step(sec,f'Диаметр вершин da{i}','da = d + 2 mn',f"{f(d)} + 2 × {f(c['m'])}",c['da'+key],'мм')
            step(sec,f'Диаметр впадин df{i}','df = d − 2,5 mn',f"{f(d)} − 2,5 × {f(c['m'])}",c['df'+key],'мм')
            step(sec,f'Основной диаметр db{i}','db = d cos αt',f"{f(d)} × cos {f(c['alphaT'])}°",c['db'+key],'мм')
            yz=p['YzLarge'] if c['da'+key]>270 else p['YzSmall']
            fp[i-1]=step(sec,f'Уточнение σFP{i} по заготовке','σFP,итог = σFP,предв Yz,итог / Yz,предв',f"{f(fp[i-1])} × {f(yz)} / {f(p['YzSmall'])}",fp[i-1]*yz/p['YzSmall'],'МПа','Т1: круглый прокат до 270 мм; выше — поковка. Предварительно по da, припуск уточнить при конструировании.')
        for title,formula,sub,value,unit in [
            ('Окружная сила','Ft = 2000 T₁ / d₁',f"2000 × {f(T)} / {f(c['d1'])}",c['Ft'],'Н'),
            ('Радиальная сила','Fr = Ft tan αt',f"{f(c['Ft'])} × tan {f(c['alphaT'])}°",c['Fr'],'Н'),
            ('Осевая сила','Fa = Ft tan β',f"{f(c['Ft'])} × tan {f(c['beta'])}°",c['Fa'],'Н'),
            ('Окружная скорость','v = π d₁ n₁ / 60000',f"π × {f(c['d1'])} × {f(speed)} / 60000",c['v'],'м/с'),
            ('Фактическая частота колеса','n₂,ф = n₁ / uф',f"{f(speed)} / {f(c['u'])}",c['n2'],'мин⁻¹'),
            ('Фактический момент колеса','T₂,ф = T₁ uф η',f"{f(T)} × {f(c['u'])} × {f(p['efficiency'])}",c['T2'],'Н·м')]: step(sec,title,formula,sub,value,unit)
        if chevron:
            axial=next(t for t in reversed(trace) if t['title']=='Осевая сила')
            axial.update(formula='Fa,сум = Fa,лев + Fa,прав',substitution=f"{f(c.get('FaLeft',c['FaHalf']))} + ({f(c.get('FaRight',-c['FaHalf']))})")
            step(sec,'Осевое усилие левой половины шеврона','Fa,лев = доля₁ Ft tan β',f"{f(c.get('FaLeft',c['FaHalf']))}",c.get('FaLeft',c['FaHalf']),'Н','По заданному распределению нагрузки; по умолчанию 50/50')
        check('Передаточное число',c['errorPct']<=p['ratioTolerance'],f"Отклонение {f(c['errorPct'])}%; допуск проекта {f(p['ratioTolerance'])}%")
        check('Замыкание геометрии',abs((c['d1']+c['d2'])/2-a)<1e-8,f"(d₁ + d₂)/2 = {f((c['d1']+c['d2'])/2)} мм; aw = {f(a)} мм")
        check('Взаимная простота',math.gcd(c['z1'],c['z2'])==1,f"НОД({c['z1']}; {c['z2']}) = 1; НОК = {c['z1']*c['z2']}")
        if not spur: check('Осевое перекрытие',c['epsilonBeta']>=1-1e-10,f"εβ = bактив sin β / (π mn) = {f(c['epsilonBeta'])} ≥ 1; для шеврона bактив = bw/2")
        check('Предварительный контроль подрезания',c['zv1']>=2/math.sin(math.radians(p['alpha']))**2,f"zv₁ = {f(c['zv1'])}; предел стандартной рейки x = 0: {f(2/math.sin(math.radians(p['alpha']))**2)}")
        table_ok=all(table_fpb(c['m'],c[f'd{i}']) is not None for i in (1,2)) and c['v']<=(12 if spur else 20)
        rp=rating_inputs(p,c)
        check('Применимость Т7 для точности 7',table_ok,f"Т7 для выбранных mn и d: fpb₁ = {rp['fpb1']} мкм, fpb₂ = {rp['fpb2']} мкм. Предельная скорость {12 if spur else 20} м/с.")
        check('Табличные коэффициенты нагрузки',True if p['factorsConfirmed'] and table_ok and p['psiBd']==.6 and c['m']<=3.5 else 'pending','Т5 исходного варианта: оба колеса консольно, выходной вал на шарикоподшипниках; ψbd = 0,6. При изменении ширины или модульной группы требуется повторный выбор проектировочных факторов.')
        rating=normative_rating(rp,c,b,T,step,check)
    status='fail' if any(c['status']=='fail' for c in checks) else 'pending' if any(c['status']=='pending' for c in checks) else 'pass'
    out=dict(errors=[],input=p,trace=trace,checks=checks,status=status,variants=variants,recommended=recommended,chosen=chosen,T=T,hp=hp,fp=fp,HP=HP,FP=FP,psi=psi,ap=ap,ac=ac,a=a,b=b,mmin=mmin,mmax=mmax,khv=khv,kfv=kfv,kha=kha,kfa=kfa,rating=rating)
    if compare and chosen:
        centers=[r10(ac),r10(r10(ac)+.01),r10(r10(r10(ac)+.01)+.01)]
        out['sizeComparison']=[]
        for center in centers:
            other=calculate({**p,'aOverride':center,'selectedModule':0})
            oc=other.get('chosen'); rt=other.get('rating') or {}
            if oc:
                out['sizeComparison'].append(dict(a=center,b=other['b'],m=oc['m'],z1=oc['z1'],z2=oc['z2'],contactMargin=rt.get('marginH'),stress=rt.get('h'),allowable=rt.get('hAllow'),tablesValid=all(table_fpb(oc['m'],oc[f'd{i}']) is not None for i in (1,2)),status=other['status']))
    return out

def calculate_json(payload):
    return json.dumps(calculate(json.loads(payload),compare=True),ensure_ascii=False,allow_nan=False)

if __name__=='__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    data=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')) if len(sys.argv)>1 else DEFAULTS
    if data.get('format')=='DriveLab': data=data['input']
    print(json.dumps(calculate(data),ensure_ascii=False,indent=2,allow_nan=False))
