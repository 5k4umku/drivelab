"""Проверка одной рабочей стороны по фактическим ступеням, приложение 3, пп. 1 и 3."""
import math
from gost_duty import equivalent_cycles, equivalent_stress
from gost_special import helical_allowable
from rating import bending_life, contact_life


def _levels(p, torque):
    rows=p['gost']['spectrum']
    if not isinstance(rows,list) or not 1<=len(rows)<=100:
        raise ValueError('Задайте от 1 до 100 ступеней циклограммы')
    levels=[]
    fractions=[]
    for i,row in enumerate(rows,1):
        if not isinstance(row,dict) or set(row)-{'timeFraction','torqueRatio','speedRatio'}:
            raise ValueError(f'Ступень {i}: ожидаются timeFraction, torqueRatio и необязательная speedRatio')
        t,f,n=row.get('torqueRatio'),row.get('timeFraction'),row.get('speedRatio',1.)
        if any(type(x) not in (float,int) or not math.isfinite(x) for x in (t,f,n)):
            raise ValueError(f'На ступени {i} требуются конечные числа')
        if not 0<f<=1 or abs(t)>100 or n<0 or (t and n==0):
            raise ValueError(f'Ступень {i}: 0<доля времени≤1, |T/Tном|≤100, для нагруженного зацепления требуется n>0')
        fractions.append(f)
        if t:
            speed=p['speed']*n
            levels.append(dict(id=i,sign=1 if t>0 else -1,torque=abs(t)*torque,speed=speed,cycles=60*speed*p['life']*f))
    if not levels or not math.isclose(math.fsum(fractions),1.,rel_tol=0,abs_tol=1e-8):
        raise ValueError('Нужна хотя бы одна нагруженная ступень. Сумма долей времени должна равняться 1')
    return levels


def _pair_allow(p,c,hp,props,speed):
    if p['gearType']=='spur':
        return min(hp)
    if not p['gost'].get('refineContact'):
        return min(1.25*min(hp),max(min(hp),.45*sum(hp)))
    alpha=c.get('alphaTW',c['alphaT'])
    cosine=math.cos(math.radians(c['alphaT']))
    return helical_allowable(z1=c['z1'],z2=c['z2'],alpha_tw=alpha,
            db1=c['d1']*cosine,db2=c['d2']*cosine,da1=c['da1'],da2=c['da2'],
            hp1=hp[0],hp2=hp[1],hv1=props[0]['hv'],hv2=props[1]['hv'],
            hb1=props[0]['hb'],hb2=props[1]['hb'],velocity=speed*math.pi*c['d1']/60000)['HP']


def _one_side(p,c,b,torque,case,step=None,check=None):
    trace,checks=[],[]
    def mark(title,status,detail):
        checks.append(dict(title=title,status=status,detail=detail))
        if check:
            check(title,status,detail)
    def emit(title,formula,sub,value,unit):
        src='ГОСТ 21354–87, приложение 3, пп. 1 и 3'
        trace.append(dict(title=title,formula=formula,substitution=sub,value=value,unit=unit,source=src))
        if step:
            step('7. Расчёт по уровням нагрузки',title,formula,sub,value,unit,src)
    def fail(message):
        mark('Расчёт по ступеням циклограммы','pending',message)
        return dict(available=False,complete=False,mandatoryPending=True,reason=message,checks=checks,trace=trace)
    try:
        levels=_levels(p,torque)
        method=p['gost']['spectrumMethod']
        if method not in ('cycles','stresses'):
            raise ValueError('Выберите метод эквивалентных циклов или напряжений')
        cfg={k:v for k,v in p['gost'].items() if k not in ('spectrum','spectrumMethod','reverseYA')}
        if p['gearType']=='spur' and p['accuracy']<=8:
            # Для всех уровней используем одинаковую схему распределения усилий.
            cfg['refineBending']=True
        if 'materials' in cfg:
            if not isinstance(cfg['materials'],list) or len(cfg['materials'])!=2:
                raise ValueError('Нужны паспорта двух венцов')
            cfg['materials']=[{**m,'muF':1.} for m in cfg['materials']]
        # Эквивалентный ресурс применяется один раз, после расчёта σ каждой ступени.
        base={**p,'gost':cfg,'loadRegime':'manual','loadDirection':'manual','muF':1.,'muH':1.,'YA':1.}
        # Проверка границ учебной таблицы скоростей зависит от ni.
        from engine import rating_inputs
        def evaluate(speed,t,startup):
            local_p={**base,'speed':speed,'startup':startup}
            local_p.pop('_tableMissing',None)
            geom={**c,'v':math.pi*c['d1']*speed/60000,'speed':speed,'n2':speed/c['u']}
            r=case(rating_inputs(local_p,geom),geom,b,t)
            if not r.get('available'):
                raise ValueError(f"Для n={speed:g} об/мин, T={t:g} Н·м: {r.get('reason','расчёт за пределами метода')}")
            return r
        results=[evaluate(level['speed'],level['torque'],1.) for level in levels]
        for level,r in zip(levels,results):
            emit(f"Ступень {level['id']}, σH",'σH(Ti,ni)',f"Ti={level['torque']:.7g} Н·м; ni={level['speed']:.7g} об/мин; Nc1={level['cycles']:.7g}",
                 r['sigmaH'],'МПа')
        r0=results[0]
        if r0.get('roots'):
            for entry in r0['trace']:
                if entry['title'] in ('Yδ1', 'Yδ2'):
                    trace.append(entry)
                    if step:
                        step('7. Расчёт по уровням нагрузки', entry['title'], entry['formula'],
                             entry['substitution'], entry['value'], entry['unit'], entry['source'])
        props=r0.get('materialProperties') or [
            dict(qF=6,NHlim=p[f'NHG{i}']*1e6,sigmaHlim=p[f'sigmaH{i}'],homogeneous=True)
            for i in (1,2)]
        traces=[{x['title']:x['value'] for x in r['trace']} for r in results]
        hp,fp,hstress,fstress,zn,yn=[],[],[],[],[],[]
        summaries=[]
        h_refs=[]
        for i,mat in enumerate(props):
            q=mat['qF']
            if q not in (6,9):
                raise ValueError(f'Для расчёта спектра нужен подтверждённый показатель qF венца {i+1}')
            rows=[dict(cycles=l['cycles']/(c['u'] if i else 1),speed=l['speed']/(c['u'] if i else 1),
                       torque=l['torque']*(c['u'] if i else 1),zv=data[f'Zv{i+1}'])
                  for l,data in zip(levels,traces)]
            if method=='cycles':
                hi=equivalent_cycles(rows,kind='contact',base_cycles=mat['NHlim'],dynamic=0.,
                                     reference_index=h_refs[0] if i else None)['referenceIndex']
                h=equivalent_cycles(rows,kind='contact',base_cycles=mat['NHlim'],dynamic=results[hi]['KHv']-1,reference_index=hi)
                h_refs.append(hi)
                h_ref=dict(torque=h['torque'],speed=h['speed'])
                fi=equivalent_cycles(rows,kind='bending',base_cycles=4e6,dynamic=0.,q=q,contact_reference=h_ref,
                                     reference_index=summaries[0]['bending']['referenceIndex'] if i else None)['referenceIndex']
                f=equivalent_cycles(rows,kind='bending',base_cycles=4e6,dynamic=results[fi]['KFv']-1,
                                    q=q,contact_reference=h_ref,reference_index=fi)
                h['stress'],f['stress']=results[hi]['sigmaH'],results[fi]['sigmaF'][i]
                h['allowableIndex'],f['allowableIndex']=hi,fi
                if f['notes']:
                    mark(f'Коэффициент μF венца {i+1}','pending',' '.join(f['notes']))
            else:
                h=equivalent_stress([dict(row,stress=r['sigmaH']) for row,r in zip(rows,results)],
                                    kind='contact',base_cycles=mat['NHlim'],limit_mpa=mat['sigmaHlim'])
                f=equivalent_stress([dict(row,stress=r['sigmaF'][i]) for row,r in zip(rows,results)],
                                    kind='bending',q=q,limit_mpa=traces[0][f'σFlimb{i+1}'])
                # Для переменной скорости базовый допуск зависит от Zv. Берём нижний
                # допуск среди учитываемых режимов, пока не применена поправка ресурса.
                for key,values,life in ((h,'hp','ZN'),(f,'fp','YN')):
                    key['allowableIndex']=min(key['included'],key=lambda j:results[j][values][i]/results[j][life][i]) if key['included'] else None
            summaries.append(dict(contact=h,bending=f))
            for entry,symbol in ((h,'H'),(f,'F')):
                emit(f'Эквивалентные циклы {symbol}{i+1}','Nэ по принятым ступеням',
                     'Ступени '+', '.join(str(levels[j]['id']) for j in entry['included']),entry['cycles'],'циклов')
                if entry['stress'] is not None:
                    description = 'Напряжение на опорной ступени' if method=='cycles' else 'Среднее по степенной сумме напряжений'
                    emit(f'Расчётное напряжение {symbol}{i+1}',description,f"Ветвь {entry['branch']}, циклов {entry['cycles']:.7g}",
                         entry['stress'],'МПа')
            zi=contact_life(mat['NHlim'],h['cycles'],mat['homogeneous']) if h['cycles'] else None
            yi=bending_life(f['cycles'],q) if f['cycles'] else None
            zh=h['allowableIndex']; yf=f['allowableIndex']
            hp.append(results[zh]['hp'][i]*zi/results[zh]['ZN'][i] if zh is not None else None)
            fp.append(results[yf]['fp'][i]*yi/results[yf]['YN'][i] if yf is not None else None)
            hstress.append(h['stress']); fstress.append(f['stress'])
            zn.append(zi); yn.append(yi)
        # Сохраняем разные σHE для шестерни и колеса. Для общего контакта берём
        # большее из них, а при уточнённых зонах проверяем все принятые скорости.
        hp_pair=None if None in hp else min(_pair_allow(p,c,hp,props,l['speed']) for l in levels)
        sigma_h=None if None in hstress else max(hstress)
        margins=dict(H=hp_pair/sigma_h if sigma_h else None,
                     F1=fp[0]/fstress[0] if fstress[0] else None,F2=fp[1]/fstress[1] if fstress[1] else None)
        extra=[]
        if method=='cycles':
            for j in summaries[0]['contact']['overloads']:
                r=results[j]
                overload_hp=[r['hp'][i]*(2.6 if a['homogeneous'] else 1.8)/r['ZN'][i] for i,a in enumerate(props)]
                allow=_pair_allow(p,c,overload_hp,props,levels[j]['speed'])
                extra.append(('H',j,allow/results[j]['sigmaH']))
            for i,summary in enumerate(summaries):
                for j in summary['bending']['overloads']:
                    r=results[j]
                    allow=r['fp'][i]*(4. if props[i]['qF']==6 else 2.5)/r['YN'][i]
                    extra.append((f'F{i+1}',j,allow/r['sigmaF'][i]))
            for key,j,margin in extra:
                margins[f"{key}over{levels[j]['id']}"]=margin
        # Момент пуска задан относительно номинального при номинальной частоте.
        # Каждая фактическая ступень (в том числе исключённые из усталости)
        # независимо участвует в поиске определяющих максимальных напряжений.
        peaks=list(results)
        if p['startup']>1:
            peaks.append(evaluate(p['speed'],torque,p['startup']))
        governing={}
        for key in ('Hmax','Fmax1','Fmax2'):
            def peak_order(k):
                margin=peaks[k]['margins'][key]
                stress=peaks[k]['hmax'] if key=='Hmax' else peaks[k]['fsmax'][int(key[-1])-1]
                return (margin is not None, margin if margin is not None else -stress)
            j=min(range(len(peaks)),key=peak_order)
            margins[key]=peaks[j]['margins'][key]
            governing[key]=j
            source=f"Ступень {levels[j]['id']}" if j<len(levels) else 'Пуск при номинальной частоте'
            stress=peaks[j]['hmax'] if key=='Hmax' else peaks[j]['fsmax'][int(key[-1])-1]
            emit(f'Определяющий максимум {key}', 'Минимальный запас среди всех фактических ступеней и пуска',
                 source,stress,'МПа')
        for key in {k for r in peaks for k in r['margins'] if k.startswith('Hdepth')}:
            values=[r['margins'].get(key) for r in peaks]
            margins[key]=min(values) if None not in values else None
        seen=set()
        ordinary=('Контактная выносливость','Изгибная выносливость','Контакт при максимуме','Изгиб шестерни при максимуме','Изгиб колеса при максимуме')
        for r in peaks:
            for item in r['checks']:
                sig=(item['title'],item['status'],item['detail'])
                if not item['title'].startswith(ordinary) and sig not in seen:
                    mark(*sig)
                    seen.add(sig)
        for key,margin in margins.items():
            if margin is None:
                mark(f'Проверка {key} по циклограмме','pending','Нет подтверждённого допуска или повреждающих ступеней по условиям приложения 3.')
            else:
                mark(f'Проверка {key} по циклограмме','pass' if margin>=1 else 'fail',f'Запас {margin:.6g}, требуется ≥1.')
        hpeak=peaks[governing['Hmax']]
        fpeak=[peaks[governing[f'Fmax{i+1}']] for i in (0,1)]
        fsmax=[r['fsmax'][i] for i,r in enumerate(fpeak)]
        fpmax=[r['fpmax'][i] for i,r in enumerate(fpeak)]
        mandatory=any(r.get('mandatoryPending') for r in peaks) or None in margins.values() or any(
                s['bending'].get('notes') for s in summaries)
        return dict(r0,h=sigma_h,sigmaH=sigma_h,HP=hp_pair,hAllow=hp_pair,hp=hp,
                    fs=fstress,sigmaF=fstress,fp=fp,fAllow=fp,marginH=margins['H'],marginF=[margins['F1'],margins['F2']],
                    sigmaHmax=hpeak['hmax'],hmax=hpeak['hmax'],hpmax=hpeak['hpmax'],hMaxAllow=hpeak['hMaxAllow'],
                    fsmax=fsmax,sigmaFmax=fsmax,fpmax=fpmax,fMaxAllow=fpmax,ZN=zn,YN=yn,margins=margins,
                    complete=all(x['status']=='pass' for x in checks),mandatoryPending=bool(mandatory),
                    method=f'gost-spectrum-{method}',trace=trace,checks=checks,
                    history=dict(levels=[dict(level,sigmaH=r['h'],sigmaF=r['fs'],sigmaHmax=r['hmax'],
                                              sigmaFmax=r['fsmax']) for level,r in zip(levels,results)],
                                 members=summaries,peakIndexes=governing,
                                 nominalLoadIndex=levels[0]['id']))
    except (ValueError,TypeError,KeyError,ArithmeticError) as error:
        return fail(str(error))


def history_rating(p,c,b,torque,case,step=None,check=None):
    """Коэффициенты противоположной амплитуды считаются по каждому венцу."""
    def reject(message):
        if check:
            check('Двусторонняя циклограмма','pending',message)
        issue=dict(title='Циклограмма',status='pending',detail=message)
        return dict(available=False,complete=False,mandatoryPending=True,checks=[issue],trace=[],reason=message)
    try:
        all_levels=_levels(p,torque)
        signs={l['sign'] for l in all_levels}
        if len(signs)==1:
            if 'reverseYA' in p['gost']:
                return reject('reverseYA относится только к двум нагружаемым сторонам.')
            return _one_side(p,c,b,torque,case,step,check)

        cfg=p['gost']
        method=cfg['spectrumMethod']
        inputs={}
        original_ids={}
        for side,sign in (('forward',1),('reverse',-1)):
            ids=[item['id'] for item in all_levels if item['sign']==sign]
            original_ids[side]=ids
            rows=[cfg['spectrum'][j-1] for j in ids]
            fraction=math.fsum(row['timeFraction'] for row in rows)
            normalized=[dict(row,timeFraction=row['timeFraction']/fraction) for row in rows]
            inputs[side]={**p,'life':p['life']*fraction,'gost':{**cfg,'spectrum':normalized}}
        if method=='cycles' and 'reverseYA' not in cfg:
            estimates={s:_one_side(data,c,b,torque,case) for s,data in inputs.items()}
            for side,r in estimates.items():
                if not r['available']:
                    return reject(r['reason'])
            props=estimates['forward']['materialProperties']
            gamma=[mat['gammaA'] for mat in props] if props else [.35,.35]
            factors=[]
            for i,g in enumerate(gamma):
                if g is None:
                    return reject('Для реверса не определён γA материала, табл. 13.10.6.1')
                amplitudes=[r['history']['members'][i]['bending']['torque']/r['YN'][i] for r in estimates.values()]
                factors.append(1-g*min(amplitudes)/max(amplitudes))
            ya={s:factors.copy() for s in inputs}
            source='Табл. 13.10.6: YA=1−γA min(TF/YN;TF′/YN′)/max(TF/YN;TF′/YN′)'
        else:
            tested=cfg.get('reverseYA')
            if (not isinstance(tested,dict) or set(tested)!={'forward','reverse','source'}
                    or not isinstance(tested['source'],str) or not tested['source'].strip()):
                return reject('Для двустороннего метода эквивалентных напряжений нужны подтверждённые YA каждой стороны: reverseYA.forward, reverseYA.reverse и источник испытаний reverseYA.source')
            ya={}
            for s in inputs:
                pair=tested[s]
                if (not isinstance(pair,list) or len(pair)!=2 or
                        any(type(y) not in (int,float) or not math.isfinite(y) or not 0<y<=1 for y in pair)):
                    return reject('На каждую сторону задайте два конечных коэффициента 0 < YA ≤ 1')
                ya[s]=pair
            source='Коэффициенты YA по данным испытаний. '+tested['source']
        rated={s:_one_side({**data,'_flankYA':ya[s]},c,b,torque,case) for s,data in inputs.items()}
        for s,r in rated.items():
            if not r['available']:
                return reject(r['reason'])
        return _merge_sides(rated,ya,source,original_ids,step,check)
    except (ValueError,KeyError,TypeError,ArithmeticError) as error:
        return reject(str(error))


def _merge_sides(rated,ya,source,ids,step,check):
    labels={'forward':'прямой ход','reverse':'обратный ход'}
    trace,checks=[],[]
    margins={}
    governing={}
    for side,r in rated.items():
        for i,y in enumerate(ya[side],1):
            title=f'YA{i}, {labels[side]}'
            item=dict(title=title,formula='Влияние двустороннего приложения нагрузки',
                      substitution=source,value=y,unit='',source='Табл. 13, п. 10.6')
            trace.append(item)
            if step:
                step('7. Двусторонняя циклограмма',title,item['formula'],source,y,'',item['source'])
        for item in r['trace']:
            item={**item,'title':f"{item['title']}, {labels[side]}"}
            trace.append(item)
            if step:
                step('7. Двусторонняя циклограмма',item['title'],item['formula'],item['substitution'],item['value'],item['unit'],item['source'])
        for item in r['checks']:
            item={**item,'title':f"{item['title']}, {labels[side]}"}
            checks.append(item)
            if check:
                check(item['title'],item['status'],item['detail'])
        for key,margin in r['margins'].items():
            # Номер кратковременной перегрузки локален в своей стороне.
            if 'over' in key:
                key=f'{key}_{side}'
            if key not in margins or margin is None or margins[key] is not None and margin<margins[key]:
                margins[key]=margin
                governing[key]=side
    h=rated[governing['H']]
    peak=rated[governing['Hmax']]
    member=[rated[governing[f'F{i}']] for i in (1,2)]
    max_member=[rated[governing[f'Fmax{i}']] for i in (1,2)]
    fs=[r['fs'][i] for i,r in enumerate(member)]
    fp=[r['fp'][i] for i,r in enumerate(member)]
    fsmax=[r['fsmax'][i] for i,r in enumerate(max_member)]
    fpmax=[r['fpmax'][i] for i,r in enumerate(max_member)]
    return dict(h,trace=trace,checks=checks,margins=margins,marginH=margins['H'],
                marginF=[margins['F1'],margins['F2']],fs=fs,sigmaF=fs,fp=fp,fAllow=fp,
                YN=[r['YN'][i] for i,r in enumerate(member)],hmax=peak['hmax'],sigmaHmax=peak['hmax'],
                hMaxAllow=peak['hMaxAllow'],hpmax=peak['hpmax'],fsmax=fsmax,sigmaFmax=fsmax,
                fpmax=fpmax,fMaxAllow=fpmax,mandatoryPending=any(r['mandatoryPending'] for r in rated.values()),
                complete=all(r['complete'] for r in rated.values()),
                history=dict(sides={s:r['history'] for s,r in rated.items()},originalRows=ids,
                             YA=ya,governing=governing))
