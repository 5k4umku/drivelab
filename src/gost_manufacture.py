"""Приработка и статистические погрешности шага по табл. 6, 10, 13 ГОСТ 21354–87."""
import math


def running_in(pitch_error, velocity, hlim, homogeneous):
    """Отдельное колесо. fpb и yα в мкм, v в м/с, σHlim в МПа."""
    if any(type(x) not in (int,float) or not math.isfinite(x) for x in (pitch_error,velocity,hlim)):
        raise ValueError('Табл. 10: нужны конечные значения погрешности, скорости и σHlim')
    if pitch_error < 0 or velocity <= 0 or hlim <= 0 or type(homogeneous) is not bool:
        raise ValueError('Табл. 10: проверьте погрешность шага, скорость и свойства материала')
    if not homogeneous:
        raw, cap = .075*pitch_error, 3.
    else:
        raw = 160*pitch_error/hlim
        cap = None if velocity < 5 else (12800 if velocity <= 10 else 6400)/hlim
    return dict(raw=raw, cap=cap, y=raw if cap is None else min(raw,cap))


def manufacture_factors(cfg, errors, velocity, materials, soft_pair):
    """Член aα fpbe и приработка yα. Изгиб по п. 5 табл. 13 использует yα=0."""
    if len(errors)!=2 or any(type(x) not in (float,int) or not math.isfinite(x) or x<0 for x in errors):
        raise ValueError('Нужны неотрицательные погрешности fpb обоих колёс в мкм')
    fpbe = math.hypot(*errors)
    evidence = cfg.get('alphaEvidence','')
    if not isinstance(evidence,str):
        raise ValueError('alphaEvidence: требуется текст с источником данных')
    lower_h = .2 if soft_pair else .3
    def alpha(stat, key, minimum, default):
        if stat in cfg:
            if key in cfg:
                raise ValueError(f'Задайте {stat} или {key} для одного критерия')
            if not evidence.strip() or not fpbe:
                raise ValueError('Для статистической погрешности нужны источник данных и ненулевой fpbe')
            value = cfg[stat]
            if type(value) not in (float,int) or not math.isfinite(value) or value < 0:
                raise ValueError('Эффективная статистическая погрешность должна быть неотрицательной')
            return max(minimum,value/fpbe), 'по эффективной погрешности пары'
        value = cfg.get(key,default)
        if type(value) not in (float,int) or not math.isfinite(value) or value < minimum:
            raise ValueError(f'Для {key} нижняя граница по твёрдости и виду проверки равна {minimum:g}')
        return value, 'по данным проекта' if key in cfg else 'по принятому значению'
    ah, source_h = alpha('pitchStatisticH','aAlpha',lower_h,1.)
    # При раздельной статистике контактной поверхности изгибу нужны собственные данные.
    default_f = 1. if 'pitchStatisticH' in cfg else max(.4,ah)
    af, source_f = alpha('pitchStatisticF','aAlphaF',.4,default_f)
    mode = cfg.get('runningInMode','manual')
    if mode not in ('table10','manual'):
        raise ValueError('runningInMode: выберите table10 или manual')
    if mode == 'table10' and 'yAlpha' in cfg:
        raise ValueError('При расчёте по табл. 10 удалите ручное значение yAlpha')
    y = cfg.get('yAlpha',0.)
    if type(y) not in (float,int) or not math.isfinite(y) or y<0:
        raise ValueError('Приработка yα должна быть конечной и неотрицательной')
    result = dict(aH=ah,aF=af,sourceH=source_h,sourceF=source_f,fpbe=fpbe,source=evidence.strip(),
                  mode=mode,member=[],y=y,yDynamics=y)
    if mode=='table10':
        if len(materials) != 2 or len(errors) != 2:
            raise ValueError('Табл. 10: нужны характеристики обоих колёс')
        pair_error = cfg.get('dynamics',{}).get('pitchError')
        dynamic_members = []
        for error, mat in zip(errors,materials):
            entry = running_in(error,velocity,mat['sigmaHlim'],mat['homogeneous'])
            result['member'].append(entry)
            dynamic_members.append(entry['y'] if pair_error is None
                                   else running_in(pair_error,velocity,mat['sigmaHlim'],mat['homogeneous'])['y'])
        result['y'] = sum(x['y'] for x in result['member'])/2
        result['yDynamics'] = sum(dynamic_members)/2
    return result
