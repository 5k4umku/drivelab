"""Номинальная геометрия внутреннего зацепления, x1=x2=0.

ГОСТ 19274–73, табл.2: da2=d2−1,6m; df2=d2+2,5m.
Это заданная геометрия, не проектировочный подбор по прочности. Параметры
долбяка, переходные поверхности, радиальная сборка и полный контроль
интерференции не определены. ГОСТ 21354–87 к этой паре не применяется.
"""
import math

SOURCE='ГОСТ 19274–73, табл.2; x₁=x₂=0, ha*=1, c*=0,25'
URL='https://files.stroyinf.ru/Data/173/17345.pdf'


def calculate_internal(p):
    p,audit=dict(p),[]
    m,z1,z2,b=p['manualModule'],int(p['manualZ1']),int(p['manualZ2']),p['manualWidth']
    beta=0 if p['gearType']=='spur' else math.radians(p['manualBeta'])
    at=math.atan(math.tan(math.radians(p['alpha']))/math.cos(beta))
    d1,d2=m*z1/math.cos(beta),m*z2/math.cos(beta)
    a=(d2-d1)/2;u=z2/z1;T=9550*p['power']/p['speed']
    da1,da2,df1,df2=d1+2*m,d2-1.6*m,d1-2.5*m,d2+2.5*m
    db1,db2=d1*math.cos(at),d2*math.cos(at)
    trace=[dict(section='0. Автоматический выбор коэффициентов',**item) for item in audit]
    checks=[]
    def step(title,formula,value,unit='',sub='',source=SOURCE):
        trace.append(dict(section='1. Заданная геометрия внутреннего зацепления',title=title,formula=formula,value=value,unit=unit,substitution=sub or f'{value:.9g}',source=source))
    def check(title,status,detail):checks.append(dict(title=title,status=status if isinstance(status,str) else 'pass' if status else 'fail',detail=detail))
    if da2<db2 or df1<=0:
        return dict(errors=['Внутреннее зацепление: da₂<db₂ или df₁≤0. Для выбранного нулевого профиля увеличьте числа зубьев.'],trace=trace,checks=[],variants=[])
    ea=(math.sqrt(da1**2-db1**2)-math.sqrt(da2**2-db2**2)+2*a*math.sin(at))/(2*math.pi*m/math.cos(beta)*math.cos(at))
    eb=(b/2 if p['gearType']=='herringbone' else b)*math.sin(beta)/(math.pi*m)
    Ft=2000*T/d1;Fr=Ft*math.tan(at);Fa=Ft*math.tan(beta)
    share=p.get('gost',{}).get('halfLoadShare',.5)
    if not isinstance(share,(int,float)) or isinstance(share,bool) or not math.isfinite(share) or not 0<share<1:
        return dict(errors=['Доля нагрузки полушеврона должна быть между 0 и 1.'],trace=trace,checks=[],variants=[])
    c=dict(meshType='internal',m=m,z1=z1,z2=z2,a=a,b=b,u=u,beta=math.degrees(beta),betaMin=0,alphaT=math.degrees(at),
        d1=d1,d2=d2,da1=da1,da2=da2,df1=df1,df2=df2,db1=db1,db2=db2,outerDiameter=df2+2*p['ringRim'],
        Ft=Ft,Fr=Fr,Fa=Fa if p['gearType']!='herringbone' else (2*share-1)*Fa,
        FaHalf=Fa/2,FaLeft=share*Fa,FaRight=-(1-share)*Fa,v=math.pi*d1*p['speed']/60000,
        n2=p['speed']/u,T2=T*u*p['efficiency'],epsilonAlpha=ea,epsilonBeta=eb,zv1=z1/math.cos(beta)**3,zv2=z2/math.cos(beta)**3,
        error=abs(u-p['ratio']),errorPct=abs(u/p['ratio']-1)*100,contactMargin=None,bendingMargin=None)
    for title,formula,value,unit,sub in [
        ('Момент шестерни','T₁=9550 P₁/n₁',T,'Н·м',f"9550×{p['power']}/{p['speed']}"),
        ('Передаточное число','u=z₂/z₁',u,'',f'{z2}/{z1}'),
        ('Торцовый угол','αt=atan(tan αn/cos β)',math.degrees(at),'°',f"atan(tan({p['alpha']}°)/cos({math.degrees(beta)}°))"),
        ('Межосевое расстояние','aw=mn(z₂−z₁)/(2cosβ)',a,'мм',f'{m}×({z2}−{z1})/(2cos({math.degrees(beta)}°))'),
        ('Ширина венца','b — заданная ширина',b,'мм',str(b)),
        ('Диаметр шестерни','d₁=mn z₁/cosβ',d1,'мм',f'{m}×{z1}/cosβ'),
        ('Диаметр внутреннего колеса','d₂=mn z₂/cosβ',d2,'мм',f'{m}×{z2}/cosβ'),
        ('Вершины шестерни','da₁=d₁+2mn',da1,'мм',f'{d1}+2×{m}'),
        ('Вершины внутреннего колеса','da₂=d₂−1,6mn',da2,'мм',f'{d2}−1,6×{m}'),
        ('Впадины шестерни','df₁=d₁−2,5mn',df1,'мм',f'{d1}−2,5×{m}'),
        ('Впадины внутреннего колеса','df₂=d₂+2,5mn',df2,'мм',f'{d2}+2,5×{m}'),
        ('Окружная сила','Ft=2000T₁/d₁',Ft,'Н',f'2000×{T}/{d1}'),
        ('Радиальная сила','Fr=Ft tanαt',Fr,'Н',f'{Ft}×tan({math.degrees(at)}°)'),
        ('Осевая сила','Fa=Ft tanβ; для шеврона Fa=(2λ−1)Ft tanβ',c['Fa'],'Н',f"Ft={Ft}; β={math.degrees(beta)}°; λ={share}"),
        ('Предварительное торцовое перекрытие','εα=(√(da₁²−db₁²)−√(da₂²−db₂²)+2aw sinαt)/(2πmt cosαt)',ea,'','Без учёта срезания и подрезания активного профиля; табл.7, п.15'),
        ('Осевое перекрытие','εβ=bактив sinβ/(πmn)',eb,'',f"bактив={b/2 if p['gearType']=='herringbone' else b}; mn={m}"),
        ('Частота колеса','n₂=n₁/u; направления вращения совпадают',c['n2'],'мин⁻¹',f"{p['speed']}/{u}")]:step(title,formula,value,unit,sub)
    check('Замыкание внутреннего зацепления',abs((d2-d1)/2-a)<1e-9,f'(d₂−d₁)/2={a:.6g} мм')
    check('Передаточное число',c['errorPct']<=p['ratioTolerance'],f"Задано {p['ratio']}; фактически {u}; отклонение {c['errorPct']:.4g} %")
    check('Предварительное перекрытие',ea>=1.2,f'εα={ea:.5g}. Значение предварительное, до проверки переходных поверхностей по табл.7.')
    check('Подрезание стандартной шестерни',c['zv1']>=2/math.sin(math.radians(p['alpha']))**2,'Контроль по стандартной рейке x=0; не заменяет проверку внутреннего зацепления с заданным долбяком.')
    check('Интерференция, срезание и сборка','pending','Нужны параметры долбяка и переходных поверхностей. Полная проверка табл.7–8 ГОСТ 19274–73 не реализована; отсутствие коллизии в 3D её не заменяет.')
    check('Прочность внутренней пары','pending','ГОСТ 21354–87 относится к внешнему зацеплению. Здесь вычислены номинальная геометрия, кинематика и силы; прочность внутренней пары не подтверждена.')
    check('Конструкция внутреннего колеса','pending','В 3D показан зубчатый обод. Диск, ступица, крепление обода и способ сборки требуют конструирования.')
    return dict(errors=[],input=p,trace=trace,checks=checks,status='fail' if any(x['status']=='fail' for x in checks) else 'pending',
        variants=[c],recommended=None,chosen=c,T=T,hp=[],fp=[],HP=None,FP=None,psi=b/a,ap=a,ac=a,a=a,b=b,mmin=m,mmax=m,
        khv=None,kfv=None,kha=None,kfa=None,rating=dict(available=False,complete=False,reason='Прочность внутреннего зацепления не рассчитывается по ГОСТ 21354–87',trace=[],checks=[]),
        sizeComparison=[],coefficientAudit=audit,geometrySource=URL)
