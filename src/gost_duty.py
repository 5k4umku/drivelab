"""Ступенчатая циклограмма одной рабочей стороны. ГОСТ 21354–87, приложение 3."""
import math


def _number(value, label, allow_zero=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero)):
        raise ValueError(f'Проверьте {label}: требуется конечное '
                         + ('неотрицательное' if allow_zero else 'положительное') + ' число')
    return value


def _settings(kind, q, threshold):
    if kind not in ('contact', 'bending'):
        raise ValueError('Укажите расчёт на контакт или изгиб')
    if kind == 'bending' and q not in (6, 9):
        raise ValueError('Показатель изгибной усталости qF должен соответствовать таблице 13 (6 или 9)')
    if threshold is None:
        return .75 if kind == 'contact' else .6
    if _number(threshold, 'αG') > 1:
        raise ValueError('Коэффициент порога повреждения должен быть не больше 1')
    return threshold


def _rows(rows):
    if not isinstance(rows, (list, tuple)) or not rows:
        raise ValueError('Задайте непустую ступенчатую циклограмму')
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f'Ступень {i+1} должна содержать именованные параметры')
        _number(row.get('cycles'), f'Nc на ступени {i+1}', allow_zero=True)
    if not any(row['cycles'] for row in rows):
        raise ValueError('Сумма чисел циклов должна быть положительной')


def equivalent_stress(rows, *, kind, limit_mpa, base_cycles=None, q=6, threshold=None):
    """Метод 3. Для одного венца и одной рабочей стороны. Напряжения — в МПа."""
    alpha = _settings(kind, q, threshold)
    _rows(rows)
    limit = _number(limit_mpa, 'предел усталости')
    if kind == 'contact':
        _number(base_cycles, 'NHlim')
    # Несколько временных интервалов одного напряжения образуют одну ступень.
    totals = {}
    for i, row in enumerate(rows):
        stress = _number(row.get('stress'), f'σ на ступени {i+1}', allow_zero=True)
        totals[stress] = totals.get(stress, 0) + row['cycles']
    cutoff = alpha * limit
    levels = {s: n for s, n in totals.items() if n > 0 and s >= cutoff
              and (kind != 'contact' or n > .03 * base_cycles)}
    included = [i for i, row in enumerate(rows) if row['stress'] in levels and row['cycles'] > 0]
    exclude_set = set(included)
    excluded = [i for i in range(len(rows)) if i not in exclude_set]
    total = math.fsum(levels.values())
    out = dict(cycles=total, included=included, excluded=excluded, cutoff=cutoff)
    if not levels:
        return dict(**out, stress=None, referenceStress=None, factor=None, branch='none')

    largest = max(levels)
    if kind == 'bending':
        exponent, branch = q, 'bending'
    elif largest < limit:
        exponent, branch = 20, 'lower'
    else:
        exponent, branch = 6, 'mixed' if min(levels) < limit else 'upper'
    # Для смешанной выборки нижняя ветвь даёт σi^20 / σlim^14.
    # Нормирование на наибольшее напряжение сохраняет точность степенной суммы.
    weighted = math.fsum((n/total) * (s/largest)**exponent
                         * ((s/limit)**14 if branch == 'mixed' and s < limit else 1)
                         for s, n in levels.items())
    equiv = largest * weighted**(1/exponent)
    first = rows[included[0]]['stress']
    return dict(**out, stress=equiv, referenceStress=first, factor=equiv/first, branch=branch)


def equivalent_cycles(rows, *, kind, base_cycles, dynamic, q=6, threshold=None,
                      reference_index=None, contact_reference=None):
    """Метод 1. Положительные Ti относятся к одной стороне зуба, ni — об/мин.

    reference_index задаёт опорную ступень со связанного элемента механизма.
    Для изгиба contact_reference задаёт TH, nH в знаменателе печатной формулы.
    """
    alpha = _settings(kind, q, threshold)
    _rows(rows)
    base = _number(base_cycles, 'базовое число циклов')
    dyn = _number(dynamic, 'динамическую добавку ν', allow_zero=True)
    levels = {}
    for i, row in enumerate(rows):
        torque = _number(row.get('torque'), f'T на ступени {i+1}', allow_zero=True)
        speed = _number(row.get('speed'), f'n на ступени {i+1}')
        zv = _number(row.get('zv'), f'Zv на ступени {i+1}') if kind == 'contact' else 1
        if row['cycles'] > 0 and torque > 0:
            indexes = levels.setdefault((torque, speed, zv), [])
            indexes.append(i)
    ordered = sorted(levels, key=lambda key: -key[0])
    if not ordered:
        raise ValueError('В циклограмме отсутствуют нагруженные ступени')
    nc = {key: math.fsum(rows[i]['cycles'] for i in ids) for key, ids in levels.items()}
    if reference_index is None:
        qualified = [key for key in ordered if (nc[key] >= .03*base if kind == 'contact' else nc[key] > 5e4)]
        if not qualified:
            raise ValueError('Нет длительной ступени для выбора расчётного момента по приложению 3')
        ref = qualified[0]
        reference_index = levels[ref][0]
    else:
        if isinstance(reference_index, bool) or not isinstance(reference_index, int):
            raise ValueError('Номер опорной ступени должен быть целым')
        ref = next((key for key, ids in levels.items() if reference_index in ids), None)
        if ref is None:
            raise ValueError('Опорная ступень отсутствует или не нагружена')
    t_ref, n_ref, zv_ref = ref
    exponent = 3 if kind == 'contact' else q
    notes = []
    if kind == 'bending':
        if not isinstance(contact_reference, dict):
            raise ValueError('Для табл. на с. 65 требуются опорные TH и nH контактного расчёта')
        th = _number(contact_reference.get('torque'), 'TH')
        nh = _number(contact_reference.get('speed'), 'nH')
        n_first = ordered[0][1]
        if th != t_ref or any(key[1] != nh for key in ordered):
            notes.append('В печатной формуле μFk на стр. 65 стоят n₁ в числителе и TH·nH в знаменателе. При отличающихся опорных режимах требуется сверка по методу эквивалентных напряжений.')

    total_cycles = math.fsum(row['cycles'] for row in rows)
    mu = 0.
    included = []
    branch = 'all'
    for k, key in enumerate(ordered):
        t, n, zv = key
        if kind == 'contact':
            relative = ((t/t_ref + dyn*n/n_ref)/(1+dyn)) * (zv_ref/zv)**2
        else:
            relative = ((t+dyn*t_ref)*n_first)/(th*(1+dyn)*nh)
        mu += nc[key] / base * relative**exponent
        included.extend(levels[key])
        if total_cycles <= base:
            continue
        boundary = alpha * mu**(1/exponent)
        if t / t_ref <= boundary:
            mu = (t / (alpha*t_ref))**exponent
            branch = 'partial'
            break
        if k+1 < len(ordered) and ordered[k+1][0]/t_ref < boundary:
            branch = 'cutoff'
            break
    overloads = [i for i, row in enumerate(rows) if row['cycles'] > 0 and row['torque'] > t_ref]
    return dict(cycles=mu*base, factor=mu, torque=t_ref, speed=n_ref,
                referenceIndex=reference_index, included=sorted(included), overloads=overloads,
                totalCycles=total_cycles, branch=branch, notes=notes)
