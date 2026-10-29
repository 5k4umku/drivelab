"""Последовательный цилиндрический редуктор. Все размеры в мм, силы в Н.

Статика: два радиальных шарнира и одна фиксирующая осевая опора на вал.
Сила приложена в полюсе зацепления: момент от Fa не теряется при переносе
на ось. Подбор подшипников, упругая линия и прочность валов не выполняются.
"""
import copy
import json
import math
from engine import DEFAULTS, calculate, f
from coefficients import layout_case, t5_factor, T5_NAMES

LAYOUTS = ('centered', 'offset', 'overhung-left', 'overhung-right', 'manual')


def new_shaft(layout='centered'):
    return dict(layout=layout, clearance=35, span=80, zA=-50, zB=50,
                diameter=20, locating='A', bearing='ball')


def from_single(data=None):
    p = {**DEFAULTS, **(data or {})}
    return dict(name='Мой редуктор', power=p['power'], speed=p['speed'], ratioTolerance=1,
                stages=[dict(input=p, angle=0, axial=0, hand='right')],
                shafts=[new_shaft('overhung-right'), new_shaft('overhung-left')])


def finite(v):
    return isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v)


def validate_project(p):
    if not isinstance(p, dict):
        return ['Проект редуктора должен быть объектом JSON.']
    errors = []
    if set(p) - {'name', 'power', 'speed', 'ratioTolerance', 'stages', 'shafts'}:
        errors.append('Проект содержит неизвестные поля.')
    if not isinstance(p.get('name'), str) or len(p['name']) > 150:
        errors.append('Название проекта: не более 150 символов.')
    if not finite(p.get('ratioTolerance', 1)) or not 0 <= p.get('ratioTolerance', 1) <= 100:
        errors.append('Допуск общего передаточного числа: 0…100 %.')
    for key, label, maximum in [('power', 'Мощность', 10000), ('speed', 'Частота', 100000)]:
        if not finite(p.get(key)) or not 0 < p[key] <= maximum:
            errors.append(f'{label} на входе должна быть положительной и в диапазоне расчётного ядра.')
    stages, shafts = p.get('stages'), p.get('shafts')
    if not isinstance(stages, list) or not 1 <= len(stages) <= 64:
        return errors + ['В проекте требуется от 1 до 64 последовательных ступеней.']
    if not isinstance(shafts, list) or len(shafts) != len(stages) + 1:
        return errors + ['Для N ступеней требуется N + 1 валов.']
    for i, s in enumerate(stages):
        prefix = f'Ступень {i + 1}: '
        if not isinstance(s, dict) or set(s) != {'input', 'angle', 'axial', 'hand'}:
            errors.append(prefix + 'неверная структура.'); continue
        if not isinstance(s['input'], dict): errors.append(prefix + 'нет исходных данных.')
        if not finite(s['angle']) or abs(s['angle']) > 36000: errors.append(prefix + 'проверьте угол компоновки.')
        if s['axial'] is not None and (not finite(s['axial']) or abs(s['axial']) > 100000):
            errors.append(prefix + 'проверьте осевую координату.')
        if s['hand'] not in ('right', 'left'): errors.append(prefix + 'неизвестное направление зуба.')
    for i, s in enumerate(shafts):
        prefix = f'Вал {i + 1}: '
        if not isinstance(s, dict) or set(s) != set(new_shaft()):
            errors.append(prefix + 'неверная структура.'); continue
        if s['layout'] not in LAYOUTS: errors.append(prefix + 'неизвестная компоновка опор.')
        if s['locating'] not in ('A', 'B'): errors.append(prefix + 'выберите фиксирующую опору A или B.')
        if s['bearing'] not in ('ball', 'roller'): errors.append(prefix + 'неизвестное обозначение опор.')
        for key in ('clearance', 'span', 'diameter', 'zA', 'zB'):
            if not finite(s[key]) or abs(s[key]) > 100000: errors.append(prefix + f'проверьте {key}.')
        if all(finite(s[k]) for k in ('clearance', 'span', 'diameter', 'zA', 'zB')):
            if s['clearance'] < 5 or s['span'] < 1 or not 1 <= s['diameter'] <= 2000:
                errors.append(prefix + 'зазор ≥ 5 мм, пролёт ≥ 1 мм, диаметр 1…2000 мм.')
            if s['layout'] == 'manual' and s['zB'] - s['zA'] < 1:
                errors.append(prefix + 'опора B должна быть правее A минимум на 1 мм.')
    return errors


def support_positions(config, gears):
    lo = min(g['z'] - g['width'] / 2 for g in gears)
    hi = max(g['z'] + g['width'] / 2 for g in gears)
    gap, span = config['clearance'], config['span']
    mode = config['layout']
    if mode == 'manual': return config['zA'], config['zB']
    if mode == 'overhung-left': return hi + gap, hi + gap + span
    if mode == 'overhung-right': return lo - gap - span, lo - gap
    if mode == 'offset': return lo - gap, hi + gap + span
    return lo - gap, hi + gap


def beam_reactions(loads, z_a, z_b, locating='A'):
    """Независимая статика с эксцентриситетом осевой силы; Н, мм, Н·м."""
    if not z_b > z_a: raise ValueError('Пролёт опор должен быть положительным.')
    total = [sum(l['force'][k] for l in loads) for k in range(3)]
    mx = sum(l['position'][1] * l['force'][2] - (l['position'][2] - z_a) * l['force'][1] for l in loads)
    my = sum((l['position'][2] - z_a) * l['force'][0] - l['position'][0] * l['force'][2] for l in loads)
    b = [-my / (z_b-z_a), mx / (z_b-z_a), -total[2] if locating == 'B' else 0]
    a = [-total[0]-b[0], -total[1]-b[1], -total[2] if locating == 'A' else 0]
    force_residual = [total[k]+a[k]+b[k] for k in range(3)]
    moment_residual = [mx-(z_b-z_a)*b[1], my+(z_b-z_a)*b[0]]
    all_loads = loads + [dict(position=[0, 0, z_a], force=a), dict(position=[0, 0, z_b], force=b)]
    stations = sorted(set(l['position'][2] for l in all_loads))
    diagram = []
    # Момент кусочно-линеен; максимум нормы достигается на концах участков.
    # Две стороны сечения сохраняют скачок момента от внеосевой Fa.
    for z in stations:
        for side in ('left', 'right'):
            left = [l for l in all_loads if l['position'][2] < z or (side == 'right' and l['position'][2] == z)]
            x = -sum(l['position'][1]*l['force'][2]-(l['position'][2]-z)*l['force'][1] for l in left)/1000
            y = -sum((l['position'][2]-z)*l['force'][0]-l['position'][0]*l['force'][2] for l in left)/1000
            diagram.append(dict(z=z, side=side, Mx=x, My=y, M=math.hypot(x, y)))
    return dict(A=dict(z=z_a, vector=a, radial=math.hypot(*a[:2]), axial=a[2]),
                B=dict(z=z_b, vector=b, radial=math.hypot(*b[:2]), axial=b[2]),
                forceResidual=force_residual, momentResidual=moment_residual,
                diagram=diagram, maxBending=max(q['M'] for q in diagram))


def calculate_assembly(project, active_index=0, _iteration=0):
    errors = validate_project(project)
    if errors: return dict(errors=errors, stages=[], shafts=[], checks=[])
    project = copy.deepcopy(project)
    stages, shafts, gears, checks, trace = [], [], [], [], []
    power, speed, ratio, efficiency = project['power'], project['speed'], 1.0, 1.0
    axis = [0.0, 0.0]
    axes = [axis]
    previous_z, previous_width = 0, 0
    for i, item in enumerate(project['stages']):
        inp = {**DEFAULTS, **item['input'], 'power': power, 'speed': speed}
        inp['title'] = f"{project['name']} · ступень {i+1}"
        try:
            r = calculate(inp, compare=i == active_index)
        except (ValueError, OverflowError, ZeroDivisionError) as error:
            return dict(errors=[f'Ступень {i+1}: параметры выходят за численную область расчёта ({error}).'], stages=[], shafts=[], checks=[])
        if r.get('errors') or not r.get('chosen'):
            return dict(errors=[f"Ступень {i+1}: " + '; '.join(r.get('errors') or ['нет допустимой геометрии; измените модули, ширину или межосевое расстояние.'])], stages=stages, shafts=[], checks=[])
        c = r['chosen']
        if c['u'] <= 1 or min(c['df1'], c['df2']) <= 0:
            return dict(errors=[f'Ступень {i+1}: недопустимая геометрия редуктора.'], stages=stages, shafts=[], checks=[])
        angle = math.radians(item['angle'])
        direction = [math.cos(angle), math.sin(angle)]
        next_axis = [axis[k] + c['a']*direction[k] for k in range(2)]
        z = item['axial'] if item['axial'] is not None else (previous_z + (previous_width+r['b'])/2 + 20 if i else 0)
        r['assemblyContext'] = dict(stage=i+1, angle=item['angle'], axial=z, hand=item['hand'])
        signs = 1 if i % 2 == 0 else -1
        hand = 1 if item['hand'] == 'right' else -1
        force = [signs*c['Ft']*direction[1] - c['Fr']*direction[0],
                 -signs*c['Ft']*direction[0] - c['Fr']*direction[1], signs*hand*c['Fa']]
        for side in (1, 2):
            center = axis if side == 1 else next_axis
            pitch = c[f'd{side}']/2
            gears.append(dict(stage=i, shaft=i+side-1, side=side, x=center[0], y=center[1], z=z,
                              width=r['b'], radius=c[f'da{side}']/2, rootRadius=c[f'df{side}']/2,
                              pitchRadius=pitch, force=force if side == 1 else [-v for v in force],
                              offset=[(1 if side == 1 else -1)*pitch*v for v in direction]))
        ratio *= c['u']; efficiency *= inp['efficiency']
        stages.append(dict(index=i, result=r, angle=item['angle'], axial=z, hand=item['hand'],
                           inputPower=power, outputPower=power*inp['efficiency'], inputSpeed=speed,
                           outputSpeed=c['n2'], totalRatio=ratio, signedInputSpeed=signs*speed))
        trace.append(dict(title=f'Ступень {i+1}: передача мощности и частоты',
                          formula='Pвыход = Pвход η; nвыход = nвход / uф',
                          detail=f"{f(power)} × {f(inp['efficiency'])} = {f(power*inp['efficiency'])} кВт; {f(speed)} / {f(c['u'])} = {f(c['n2'])} мин⁻¹"))
        power *= inp['efficiency']; speed = c['n2']
        axis = next_axis; axes.append(axis)
        previous_z, previous_width = z, r['b']
    def check(title, status, detail):
        checks.append(dict(title=title, status=status if isinstance(status, str) else 'pass' if status else 'fail', detail=detail))
    for i, config in enumerate(project['shafts']):
        own = [g for g in gears if g['shaft'] == i]
        za, zb = support_positions(config, own)
        loads = [dict(position=[*g['offset'], g['z']], force=g['force'], stage=g['stage'], side=g['side']) for g in own]
        statics = beam_reactions(loads, za, zb, config['locating'])
        shaft_power = project['power'] if i == 0 else stages[i-1]['outputPower']
        shaft_speed = project['speed'] if i == 0 else stages[i-1]['outputSpeed']
        bearing_width = max(8, config['diameter']*.45)
        lo = min(za-bearing_width, *(g['z']-g['width']/2 for g in own))-config['diameter']
        hi = max(zb+bearing_width, *(g['z']+g['width']/2 for g in own))+config['diameter']
        shafts.append(dict(index=i, x=axes[i][0], y=axes[i][1], diameter=config['diameter'],
                           zMin=lo, zMax=hi, bearingWidth=bearing_width, bearing=config['bearing'],
                           locating=config['locating'], layout=config['layout'], speed=shaft_speed,
                           signedSpeed=(-1 if i % 2 else 1)*shaft_speed, power=shaft_power,
                           torque=9550*shaft_power/shaft_speed, loads=loads, **statics))
        check(f'Вал {i+1}: равновесие сил и изгибающих моментов',
              max(map(abs, statics['forceResidual']+statics['momentResidual'])) < 1e-6,
              f"ΣF ≤ {f(max(map(abs,statics['forceResidual'])),9)} Н; ΣMxy ≤ {f(max(map(abs,statics['momentResidual'])),9)} Н·мм.")
        for g in own:
            check(f"Вал {i+1}, ступень {g['stage']+1}: посадка колеса",
                  config['diameter'] < 2*g['rootRadius'],
                  f"Диаметр вала {f(config['diameter'])} мм; диаметр впадин {f(2*g['rootRadius'])} мм. Толщина обода и шпонка требуют отдельного расчёта.")
            overlap = [name for name, z in [('A', za), ('B', zb)] if abs(z-g['z']) < (g['width']+bearing_width)/2]
            check(f"Вал {i+1}, ступень {g['stage']+1}: опоры вне венца", not overlap,
                  'Пересечение условных габаритов опор: '+', '.join(overlap) if overlap else 'Условные опоры не пересекают венец по оси Z.')
    # Т5 зависит от фактической компоновки. Пересчитываем геометрию после
    # выбора коэффициента; ручные опоры при этом остаются на своих местах.
    updated = False
    for i, stage in enumerate(stages):
        inp = stage['result']['input']
        if inp.get('faceMode') != 'seminar': continue
        case = layout_case(stage['axial'], shafts[i:i+2], stage['result']['chosen']['Fa'])
        tab = t5_factor(inp['psiBd'], case) if inp['treatment1'] == inp['treatment2'] == 'У' else None
        if tab is None:
            return dict(errors=[f'Ступень {i+1}: Т5 не задаёт коэффициент для «{T5_NAMES[case]}», ψbd={f(inp["psiBd"])}. Измените ширину либо задайте коэффициенты по обоснованной методике.'], stages=[], shafts=[], checks=[])
        value = tab['value']
        stage['faceSelection'] = dict(case=case, label=T5_NAMES[case], **tab)
        if any(abs(inp[k]-value)>1e-9 for k in ('KHbeta','KFbeta')):
            project['stages'][i]['input'].update(KHbeta=value,KFbeta=value,factorsConfirmed=False)
            updated = True
        source = 'Т5 семинара, У / У; линейная интерполяция соседних строк'
        detail = f"{T5_NAMES[case]}; ψbd={f(inp['psiBd'])}; строки {f(tab['lower'])}…{f(tab['upper'])}; KHβ≈KFβ={f(value)}."
        stage['result']['trace'].insert(0,dict(section='0. Автоматический выбор коэффициентов',title='KHβ≈KFβ по компоновке',formula='K=K₀+(K₁−K₀)(ψ−ψ₀)/(ψ₁−ψ₀)',substitution=detail,value=value,unit='',source=source))
        check(f'Ступень {i+1}: выбор Т5', 'pending', detail+' Учебное приближение; не заменяет расчёт перекоса по ГОСТ.')
    if updated:
        if _iteration >= 8:
            return dict(errors=['Выбор Т5 и компоновки не сошёлся за 9 пересчётов. Зафиксируйте опоры или задайте коэффициенты вручную.'], stages=[], shafts=[], checks=[])
        return calculate_assembly(project, active_index, _iteration+1)
    collisions = []
    for index, a in enumerate(gears):
        for b in gears[index+1:]:
            if a['stage'] == b['stage']: continue  # Предусмотренное зацепление.
            if abs(a['z']-b['z']) < (a['width']+b['width'])/2 - 1e-8 and math.hypot(a['x']-b['x'], a['y']-b['y']) < a['radius']+b['radius']-1e-8:
                collisions.append(f"венцы ступеней {a['stage']+1} и {b['stage']+1}")
        for s in shafts:
            if s['index'] == a['shaft']: continue
            # У сопряжённого колеса вал тоже может задевать зубья партнёра.
            if min(s['zMax'], a['z']+a['width']/2) > max(s['zMin'], a['z']-a['width']/2) and math.hypot(a['x']-s['x'], a['y']-s['y']) < a['radius']+s['diameter']/2-1e-8:
                collisions.append(f"венец ступени {a['stage']+1} и вал {s['index']+1}")
    for i, a in enumerate(shafts):
        for b in shafts[i+1:]:
            if min(a['zMax'], b['zMax']) > max(a['zMin'], b['zMin']) and math.hypot(a['x']-b['x'], a['y']-b['y']) < (a['diameter']+b['diameter'])/2-1e-8:
                collisions.append(f"валы {a['index']+1} и {b['index']+1}")
    collisions = list(dict.fromkeys(collisions))
    check('Пересечения габаритов деталей', not collisions,
          '; '.join(collisions) if collisions else 'Габариты несопряжённых венцов и валов не пересекаются. Посадки, ступени валов и реальные подшипники проверяются при деталировке.')
    check('Коэффициенты распределения нагрузки по ширине', 'pending',
          'KHβ и KFβ каждой ступени заданы отдельно. Реакции опор не заменяют расчёт жёсткости валов, корпуса и перекоса зубьев. После смены компоновки требуется уточнить коэффициенты.')
    check('Прочность валов и ресурс подшипников', 'pending',
          'Выполнена статическая схема двух опор. Номера подшипников, концентрация напряжений, усталость, прогибы, масса деталей и внешние нагрузки на концы валов в эту модель не входят.')
    check('Область конструктора', 'pending',
          'Последовательные внешние цилиндрические зацепления на параллельных валах, x₁ = x₂ = 0. Внутреннее зацепление, разветвление потока мощности и упругие многоопорные валы требуют других моделей.')
    check('Баланс мощности', abs(power-project['power']*efficiency) < 1e-8,
          f"Pвыход = {f(power)} кВт; потери = {f(project['power']-power)} кВт; ηΣ = {f(efficiency)}.")
    target_ratio = math.prod(s['result']['input']['ratio'] for s in stages)
    ratio_error = abs(ratio/target_ratio-1)*100
    check('Общее передаточное число', ratio_error <= project.get('ratioTolerance', 1),
          f"Задано {f(target_ratio)}; фактически {f(ratio)}; отклонение {f(ratio_error)} %; допуск {f(project.get('ratioTolerance', 1))} %.")
    extrema = [min(g['x']-g['radius'] for g in gears), max(g['x']+g['radius'] for g in gears),
               min(g['y']-g['radius'] for g in gears), max(g['y']+g['radius'] for g in gears),
               min(s['zMin'] for s in shafts), max(s['zMax'] for s in shafts)]
    statuses = [c['status'] for c in checks] + [s['result']['status'] for s in stages]
    return dict(errors=[], project=project, stages=stages, shafts=shafts, gears=gears,
                checks=checks, trace=trace, collisions=collisions, bounds=extrema,
                totalRatio=ratio, targetRatio=target_ratio, ratioError=ratio_error, efficiency=efficiency, outputPower=power, outputSpeed=speed,
                outputTorque=9550*power/speed, lostPower=project['power']-power,
                status='fail' if 'fail' in statuses else 'pending' if 'pending' in statuses else 'pass')


def assembly_json(payload):
    data=json.loads(payload)
    return json.dumps(calculate_assembly(data['project'], data.get('activeStage', 0)), ensure_ascii=False, allow_nan=False)
