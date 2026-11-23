"""Альтернативные критерии таблиц 1–2: запас, ресурс и вероятность."""
import math


def probability_lower(successes, total, confidence):
    """Точная односторонняя граница для независимых испытаний Бернулли."""
    if successes == 0:
        return 0.
    if successes == total:
        return (1-confidence)**(1/total)
    coeff=[math.lgamma(total+1)-math.lgamma(k+1)-math.lgamma(total-k+1) for k in range(successes,total+1)]
    lo,hi=0.,1.
    for _ in range(50):
        p=(lo+hi)/2
        logs=[v+k*math.log(p)+(total-k)*math.log1p(-p) for k,v in enumerate(coeff,successes)]
        top=max(logs)
        tail_log=top+math.log(math.fsum(math.exp(v-top) for v in logs))
        if tail_log < math.log1p(-confidence): lo=p
        else: hi=p
    return (lo+hi)/2


def add_criteria(result, spec, p, rerate, emit, verify):
    if not isinstance(spec,dict) or set(spec)-{'lifeLimitHours','trials'} or not spec:
        raise ValueError('criteria: задайте lifeLimitHours и/или trials.')
    out={}
    if 'lifeLimitHours' in spec:
        cap=spec['lifeLimitHours']
        if type(cap) not in (int,float) or not p['life']<=cap<=1e7:
            raise ValueError('Верхняя граница поиска ресурса должна лежать между заданным ресурсом и 10⁷ ч.')
        if p.get('gost',{}).get('spectrum') or p.get('loadDirection')=='reversing' or (p.get('loadDirection')=='manual' and p['YA']!=1):
            raise ValueError('Поиск предельного ресурса рассчитан на фиксированный односторонний режим.')
        keys=('H','F1','F2')
        def margin_at(hours):
            r=rerate(hours)
            if not r.get('available'):
                raise ValueError('Проверка ресурса: '+r.get('reason','отсутствуют данные.'))
            return min(r['margins'][k] for k in keys)
        lo,hi=1e-6,cap
        if margin_at(cap)>=1: hours,bound=cap,'atLeast'
        elif margin_at(lo)<1: hours,bound=lo,'lessThan'
        else:
            for _ in range(46):
                mid=(lo+hi)/2
                if margin_at(mid)>=1: lo=mid
                else: hi=mid
            hours,bound=lo,'limit'
        out['life']=dict(hours=hours,bound=bound,searchLimit=cap)
        text={'atLeast':'не менее','lessThan':'менее','limit':'около'}[bound]
        emit('Расчётный ресурс поверхности и корня','NL ≥ NK при одновременной проверке σH, σF1, σF2',
             f'Lрасч {text} {hours:.7g} ч; граница поиска {cap:.7g} ч; пики проверяются отдельно.',hours,'ч','Табл. 1–2, условия (10), (25); обращение кривых долговечности')
        ok=all(result['margins'][k]>=1 for k in keys)
        verify('Ресурс зубьев при заданном режиме', 'pass' if ok else 'fail',
               f'Требуется {p["life"]:.7g} ч, по поверхностной и изгибной выносливости {text} {hours:.7g} ч.')
    if 'trials' in spec:
        trials=spec['trials']
        names={'H':'контактная усталость','F':'усталость корня','HSt':'пиковый контакт','FSt':'пиковый изгиб'}
        if not isinstance(trials,dict) or not trials or set(trials)-names.keys():
            raise ValueError('Испытания задаются по критериям H, HSt, F и FSt.')
        out['trials']={}
        for key,v in trials.items():
            if not isinstance(v,dict) or set(v)!={'passed','total','minimum','confidence','source'}:
                raise ValueError('Серия испытаний требует passed, total, minimum, confidence и source.')
            a,n=v['passed'],v['total']
            confidence,target=v['confidence'],v['minimum']
            if type(a)!=int or type(n)!=int or not 0<=a<=n<=2000 or n<1:
                raise ValueError('Серия должна содержать 1…2000 независимых испытаний и число успешных исходов.')
            if any(type(x) not in (int,float) or not 0<x<1 for x in (confidence,target)) or not isinstance(v['source'],str) or not v['source'].strip():
                raise ValueError('Укажите вероятность, доверительный уровень и протокол испытаний.')
            lower=probability_lower(a,n,confidence)
            ok=lower>target if key.endswith('St') else lower>=target
            emit('Вероятность: '+names[key],'Pнижн — односторонняя точная биномиальная граница',
                 f'{a} из {n}; доверительный уровень {confidence:g}; {v["source"][:1000]}',lower,'','ГОСТ, (12), (13), (27), (28); статистическая модель Клоппера–Пирсона')
            verify('Испытания: '+names[key],'pass' if ok else 'fail',
                   f'Нижняя граница {lower:.6g}, требование {">" if key.endswith("St") else "≥"} {target:g}.')
            out['trials'][key]=dict(lower=lower,observed=a/n,target=target)
    return out
