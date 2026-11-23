"""Приложение 10. Эквивалентные моменты и сравнение с типовыми распределениями."""
import math

# μH, μF для qF=6 и 9 — таблица 36. Коэффициенты циклов табл. 35 иные.
RATIOS={'0':(1.,1.,1.),'I':(.80,.82,.84),'II':(.63,.72,.77),
        'III':(.56,.63,.69),'IV':(.50,.58,.63),'V':(.40,.48,.54)}


def cdf(regime, x):
    if regime=='0': return float(x>=1)
    if regime=='II': return x
    if regime=='III': return (1+math.erf((x-.5)/(.19*math.sqrt(2))))/2
    a,b={'I':(6.8,2),'IV':(2.2,3),'V':(1.8,4)}[regime]
    # При целом b интеграл (57) сводится к конечной сумме.
    integral=sum((-1)**j*math.comb(b-1,j)*x**(a+j)/(a+j) for j in range(b))
    return integral*math.exp(math.lgamma(a+b)-math.lgamma(a)-math.lgamma(b))


def nearest_regime(rows):
    """Среднеквадратичное расхождение функций распределения на шкале T/Tmax."""
    sides={}
    for sign in (1,-1):
        data=[(abs(r['torqueRatio']),r['timeFraction']*r.get('speedRatio',1))
              for r in rows if r['torqueRatio']*sign>0]
        if not data: continue
        maximum=max(t for t,_ in data)
        total=sum(w for _,w in data)
        errors={k:0 for k in RATIOS}
        for j in range(100):
            x=(j+.5)/100
            actual=sum(w for t,w in data if t/maximum<=x)/total
            for key in errors: errors[key]+=(cdf(key,x)-actual)**2/100
        key=min(errors,key=errors.get)
        sides[sign]=dict(regime=key,rms=math.sqrt(errors[key]))
    return sides

