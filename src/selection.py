"""Подбор зубьев по алгоритму Zubil.html Павла Зарубова.

Независимая реализация на Python: floor/ceil для каждой суммы зубьев,
максимальный НОК внутри допуска, ближайшая пара при отсутствии решения.
НОК описывает повторяемость контакта, а не является проверкой прочности.
"""
import math


def tooth_pairs(low, high, ratio, tolerance=3):
    for value in (low,high,ratio,tolerance):
        if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value):
            raise ValueError('Задайте конечные числовые границы, отношение и допуск.')
    if min(low,high)<2 or max(low,high)>100000 or ratio<1 or tolerance<0 or tolerance>100:
        raise ValueError('Сумма зубьев: 2…100000; u≥1; допуск: 0…100 %.')
    start,end=math.ceil(min(low,high)),math.floor(max(low,high))
    if start>end or end-start>10000: raise ValueError('Нужны целые суммы зубьев; не более 10001 значения.')
    pairs=[]
    for total in range(start,end+1):
        exact=total/(ratio+1)
        for z1 in sorted({math.floor(exact),math.ceil(exact)}):
            z2=total-z1
            if z1<1 or z2<z1: continue
            gcd=math.gcd(z1,z2)
            error=abs(z2/z1-ratio)/ratio*100
            pairs.append(dict(total=total,z1=z1,z2=z2,u=z2/z1,errorPct=error,
                gcd=gcd,lcm=z1*z2//gcd,turns=z2//gcd,within=error<=tolerance+1e-12))
    return pairs


def zubil(low,high,ratio,tolerance=3):
    pairs=tooth_pairs(low,high,ratio,tolerance)
    valid=[p for p in pairs if p['within']]
    best=min(valid,key=lambda p:(-p['lcm'],p['errorPct'],p['total'],p['z1'])) if valid else min(pairs,key=lambda p:(p['errorPct'],-p['lcm']),default=None)
    return dict(pairs=pairs,best=best,withinTolerance=bool(valid),count=len(pairs),
        source='Zubil.html · Павел Зарубов; перенос алгоритма на Python',
        note='Кинематический подбор. Подрезание, модуль, перекрытие и прочность здесь не проверяются.')
