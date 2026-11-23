"""Основные зависимости (1)–(30) для металлической пары с известными свойствами.

Коэффициенты материала, долговечности и нагрузки в этом способе назначают по
расчёту или испытаниям конкретного проекта. Автоматические таблицы для стали
относятся к другой методике — приложению 1.
"""
import math


def basic_rating(p,c,b,T,spec,step=None,check=None):
    trace,checks=[],[]
    def emit(title,formula,sub,value,unit,page):
        source='ГОСТ 21354–87, '+page
        trace.append(dict(title=title,formula=formula,substitution=sub,value=value,unit=unit,source=source))
        if step: step('7. Основные зависимости ГОСТ',title,formula,sub,value,unit,source)
    def verify(title,status,detail):
        checks.append(dict(title=title,status=status,detail=detail))
        if check: check(title,status,detail)
    def exact(record,keys):
        if not isinstance(record,dict) or set(record)!=set(keys.split()):
            raise ValueError('Ожидаются поля '+keys)
    def number(record,key):
        val=record[key]
        if type(val) not in (float,int) or not math.isfinite(val) or val<=0:
            raise ValueError(key+' должно быть положительным конечным числом.')
        return val
    def reject(message):
        verify('Исходные данные основной методики','pending',message)
        return dict(available=False,complete=False,reason=message,checks=checks,trace=trace)
    try:
        exact(spec,'source wheels nominal peak Zbeta Ybeta Yepsilon')
        if not isinstance(spec['source'],str) or not spec['source'].strip():
            raise ValueError('Укажите обоснование нагрузок и технологических коэффициентов.')
        wheels=spec['wheels']
        if not isinstance(wheels,list) or len(wheels)!=2:
            raise ValueError('Для основной методики укажите два материала.')
        if p.get('meshType','external')!='external' or c['v']>25 or c['m']<1 or not p.get('gost',{}).get('oil',True):
            raise ValueError('Область стандарта: внешнее зацепление, m≥1 мм, v≤25 м/с и масляная смазка.')
        if p.get('geometryMode')!='given' or p.get('alpha')!=20 or c['epsilonAlpha']<1:
            raise ValueError('Для основных зависимостей укажите внешнюю пару по чертежу, стандартную рейку 20° и εα≥1.')
        if p['gearType']=='herringbone':
            share=p.get('gost',{}).get('halfLoadShare',.5)
            T=T*max(share,1-share)
            b=b/2
        if p['startup']<1: raise ValueError('Пиковый момент не может быть ниже рабочего.')
        zb,yb,ye=[number(spec,k) for k in ('Zbeta','Ybeta','Yepsilon')]
        mats=[]
        for w in wheels:
            keys='label source E nu sigmaHlim ZN ZL ZR Zv ZW ZX SH sigmaHSt SHSt sigmaFlimb YN YR YX Ydelta SF sigmaFSt SFSt YdeltaSt YdeltaStT YFS'
            exact(w,keys)
            if any(not isinstance(w[k],str) or not w[k].strip() for k in ('label','source')):
                raise ValueError('Каждому колесу нужны материал и источник его свойств.')
            mat={k:number(w,k) for k in keys.split() if k not in ('label','source','nu')}
            nu=w['nu']
            if type(nu) not in (float,int) or not -1<nu<.5 or min(mat[k] for k in ('SH','SHSt','SF','SFSt'))<1:
                raise ValueError('Проверьте коэффициент Пуассона и минимальные коэффициенты запаса.')
            mat.update(nu=nu,label=w['label'],source=w['source'])
            mats.append(mat)
        ze=1/math.sqrt(math.pi*sum((1-w['nu']**2)/w['E'] for w in mats))
        at,aw,bb=[math.radians(c[k]) for k in ('alphaT','alphaTW','betaB')]
        zh=math.sqrt(2*math.cos(bb)/math.tan(aw))/math.cos(at)
        ea,eb=c['epsilonAlpha'],c['epsilonBeta']
        zep=math.sqrt((4-ea)*(1-eb)/3+eb/ea if eb<1 else 1/ea)
        ft=2000*T/c['d1']
        def loads(obj,ka,t):
            exact(obj,'KHv KHbeta KHalpha KFv KFbeta KFalpha')
            kh,kf=[ka*math.prod(number(obj,k+suffix) for suffix in ('v','beta','alpha')) for k in ('KH','KF')]
            h=ze*zh*zep*zb*math.sqrt(t*kh*(c['u']+1)/(b*c['d1']*c['u']))
            fs=[t*kf*w['YFS']*yb*ye/(b*c['m']) for w in mats]
            return h,fs,kh,kf
        h,fs,kh,kf=loads(spec['nominal'],p['KA'],ft)
        hst,fst,khst,kfst=loads(spec['peak'],1,ft*p['startup'])
        hp=[w['sigmaHlim']*math.prod(w[k] for k in ('ZN','ZL','ZR','Zv','ZW','ZX'))/w['SH'] for w in mats]
        fp=[w['sigmaFlimb']*math.prod(w[k] for k in ('YN','YR','YX','Ydelta'))/w['SF'] for w in mats]
        hpmax=[w['sigmaHSt']/w['SHSt'] for w in mats]
        fpmax=[w['sigmaFSt']*w['YdeltaSt']/w['YdeltaStT']/w['SFSt'] for w in mats]
        margins=dict(H=min(hp)/h,F1=fp[0]/fs[0],F2=fp[1]/fs[1],Hmax=min(hpmax)/hst,Fmax1=fpmax[0]/fst[0],Fmax2=fpmax[1]/fst[1])
        emit('ZE','ZE=1/√(πΣ(1−ν²)/E)',str([(w['E'],w['nu']) for w in mats]),ze,'√МПа','табл. 6, п. 1')
        for mode,factor,force,stress,ff in [('Рабочая нагрузка',kh,ft,h,fs),('Максимум',khst,ft*p['startup'],hst,fst)]:
            emit('Контакт · '+mode,'σH=ZE ZH Zε Zβ √(Ft KH (u+1)/(b d₁ u))',f'Ft={force:.7g}; KH={factor:.7g}; ZH={zh:.7g}; Zε={zep:.7g}; Zβ={zb:.7g}',stress,'МПа','(1)–(3)')
            for i,w in enumerate(mats):
                emit(f'Изгиб {i+1} · '+mode,'σF=Ft KF YFS Yβ Yε/(b mn)',f"Ft={force:.7g}; KF={(kf if mode=='Рабочая нагрузка' else kfst):.7g}; YFS={w['YFS']}",ff[i],'МПа','(16)–(17)')
        for i,w in enumerate(mats):
            for name,actual,limit,required,page in [('SH',h,hp[i],w['SH'],'(4), (8), (14)'),('SHSt',hst,hpmax[i],w['SHSt'],'(5), (9), (15)'),
                 ('SF',fs[i],fp[i],w['SF'],'(18), (23), (29)'),('SFSt',fst[i],fpmax[i],w['SFSt'],'(19), (24), (30)')]:
                safety=limit*required/actual
                emit(f'{name}, колесо {i+1}', 'Sрасч = σдоп Smin / σрасч',f'{limit:.7g} × {required:.7g} / {actual:.7g}',safety,'',page)
                verify(f'{name} · '+w['label'],'pass' if safety>=required else 'fail',
                       f"Sрасч={safety:.7g}, требуется {required:.7g}; {w['source']}.")
        return dict(available=True,complete=all(x['status']=='pass' for x in checks),method='basic-equations',trace=trace,checks=checks,
                    margins=margins,marginH=margins['H'],marginF=[margins['F1'],margins['F2']],h=h,fs=fs,hAllow=min(hp),fAllow=fp,
                    hmax=hst,fsmax=fst,hMaxAllow=min(hpmax),fMaxAllow=fpmax,hp=hp,fp=fp,hpmax=hpmax,fpmax=fpmax,
                    KH=kh,KF=kf,KHbeta=spec['nominal']['KHbeta'],KFbeta=spec['nominal']['KFbeta'],
                    assumptions=[spec['source']],mandatoryPending=False)
    except (TypeError,KeyError,ValueError,ArithmeticError) as exc:
        return reject(str(exc))

