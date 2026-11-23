"""Материальные характеристики одного венца по приложению 1 ГОСТ 21354–87."""
import math


# Строку назначает технолог по составу стали и маршруту обработки.
# Порядок полей: диапазон твёрдости, базовый предел, SF для P=0,99,
# Yg при гарантированном качестве шлифования и при отсутствии гарантии,
# диапазоны Yd при наклёпе нешлифованной и шлифованной переходной поверхности.
ROWS = {
    '14.1': ((57,63),950,1.55,(.75,.6),((1,1.05),(1.1,1.3))),
    '14.2': ((57,63),820,1.55,(.75,.65),((1,1.1),(1.1,1.3))),
    '14.3': ((56,63),800,1.65,(.8,.65),((1.1,1.2),(1.15,1.3))),
    '14.4': ((55,63),780,1.70,(.8,.65),((1.1,1.2),(1.15,1.3))),
    '14.5': ((55,63),680,1.70,(.8,.7),((1.1,1.2),(1.15,1.3))),
    '15.1': ((57,63),1000,1.55,(.7,.525),((1,1),(1,1.35))),
    '15.2': ((57,63),750,1.55,(.75,.5625),((1.05,1.1),(1.1,1.35))),
    '16.1': ((180,350),None,1.70,(1.1,1.1),((1.1,1.3),(1.1,1.3))),
    '16.2': ((45,55),580,1.70,(.9,.75),((1.05,1.15),(1.1,1.2))),
    '16.3': ((45,55),500,1.70,(1,.8),((1.1,1.3),(1.1,1.2))),
    '16.4': ((45,55),460,1.70,(1,.8),((1.1,1.3),(1.1,1.2))),
    '16.5': ((700,950),None,1.70,None,None),
    '16.6': ((550,750),None,1.70,None,None),
    '17.1': ((58,62),870,1.70,(.75,.55),((1,1),(1.1,1.2))),
    '17.2': ((54,60),730,1.70,(.8,.7),((1,1),(1.1,1.2))),
    '17.3': ((48,58),680,1.70,(1,.8),((1.05,1.1),(1.1,1.2))),
    '17.4': ((48,58),580,1.70,(1,.8),((1.05,1.1),(1.1,1.2))),
    '17.5': ((48,55),580,1.70,(1,.8),((1.15,1.35),(1.1,1.2))),
    '17.6': ((48,55),480,1.70,(1,.8),((1.15,1.35),(1.1,1.2))),
    '17.7': ((200,300),390,1.70,(1,.8),((1.2,1.4),(1.1,1.3))),
}


def number(data, key, low=0, high=math.inf):
    x = data.get(key)
    if (type(x) not in (int, float) or not math.isfinite(x) or
            x <= 0 or not low <= x <= high):
        raise ValueError(f'{key}: требуется положительное число в диапазоне {low:g}…{high:g}')
    return x


def flag(data, key):
    x = data.get(key)
    if type(x) is not bool:
        raise ValueError(f'{key}: требуется явное подтверждение true или false')
    return x


def material_properties(mat, module):
    """Паспорт отдельного венца; HB и HV задают в своих шкалах (черт. 8).

    evidence указывает документ, подтверждающий химсостав, режим, строку
    таблицы и наличие/отсутствие технологических отклонений.
    """
    if not isinstance(mat, dict):
        raise ValueError('Паспорт материала должен быть объектом')
    known = {'row','label','evidence','hb','hv','hrc','coreHrc','rootHrc','rootHB',
             'yieldStrength','blank','grinding','rootTreatment','technologyCompliant',
             'goodGrinding','YD','SH','SF','lowTempering','contactPatternGrade','flankRa',
             'smoothSpectrum','darkPhaseAbsent','specialTests','highTemperProtected',
             'qF','muF','peakRow','carbon','nitrogen','caseDepth','grainSize','noFerrite',
             'nitridesAbsent','table19Inapplicable','testedPeakContact','polishedBeforeTreatment','YR',
             'severeConsequences'}
    unknown = set(mat) - known
    if unknown:
        raise ValueError(f'Неизвестные поля паспорта: {", ".join(sorted(unknown))}')
    for k in ('label','evidence'):
        if not isinstance(mat.get(k), str) or not mat[k].strip():
            raise ValueError(f'{k}: укажите материал и основание выбора строки')
    row = mat.get('row')
    if not isinstance(row, str) or row not in ROWS:
        raise ValueError('Выберите строку таблиц 14–17, например 16.1')
    table = int(row.split('.')[0])
    hard_range, flim, sf_min, grinding, peening = ROWS[row]
    blank = mat.get('blank')
    blank_factor = {'forged':1., 'stamped':1., 'rolled':.9, 'cast':.8}
    if blank not in blank_factor:
        raise ValueError('blank: укажите forged, stamped, rolled или cast (табл. 13.10.3)')
    hb = number(mat,'hb',1,1000)
    hv = number(mat,'hv',1,1500)
    normal = row == '16.1'
    bulk = row in ('16.2','16.3','16.4')
    nitrided = row in ('16.5','16.6')
    contour = row in ('17.1','17.2','17.3','17.4')
    case_hardened = table in (14,15)
    homogeneous = normal or bulk
    hrc = None if normal or nitrided else number(mat,'hrc',1,70)
    if hrc is not None and hrc >= 45 and hv <= 350:
        raise ValueError('Твёрдость ≥45 HRCэ не согласована с HV≤350, см. черт. 8')
    if normal:
        number(mat,'hb',*hard_range)
        if hb >= 350:
            raise ValueError('Табл. 12, строка 1: средняя твёрдость должна быть ниже 350 HB')
        flim = 1.75 * hb
        hlim, hformula = 2 * hb + 70, '2 HB + 70'
    elif nitrided:
        number(mat,'hv',*hard_range)
        grade = number(mat,'contactPatternGrade',1,12)
        if hv > 750 or number(mat,'flankRa') > 1.25 or grade != int(grade) or grade > 6:
            raise ValueError('Азотирование: табл. 11–12 требуют 550…750 HV, Ra≤1,25 мкм и пятно контакта по 6-й степени или точнее')
        flim = 290 + 12 * number(mat,'coreHrc',24,40)
        hlim, hformula = 1050., '1050 МПа (азотирование)'
    elif case_hardened:
        number(mat,'hrc',*hard_range)
        if hrc <= 56:
            raise ValueError('Табл. 12, строка 3: твёрдость поверхности должна превышать 56 HRCэ')
        hlim, hformula = 23 * hrc, '23 HRCэ'
    else:
        number(mat,'hrc',38,50)
        hard_key = 'hrc' if bulk else 'rootHB' if row == '17.7' else 'rootHrc'
        number(mat,hard_key,*hard_range)
        if contour:
            number(mat,'coreHrc',28 if row=='17.1' else 25,35)
        hlim, hformula = 17 * hrc + 200, '17 HRCэ + 200'
    if normal or bulk:
        if bulk and not flag(mat,'lowTempering'):
            raise ValueError('Для σHPmax=2,8σт при сквозной закалке требуется низкий отпуск, п. 3.2.2')
        hpmax, peak_h_formula = 2.8 * number(mat,'yieldStrength'), '2,8 σт'
    elif nitrided:
        hpmax, peak_h_formula = 3 * hv, '3 HV'
    elif table == 14 or contour:
        hpmax, peak_h_formula = 44 * hrc, '44 HRCэ'
    elif row in ('17.5','17.6','17.7') and flag(mat,'lowTempering'):
        hpmax, peak_h_formula = 2.8 * number(mat,'yieldStrength'), '2,8 σт'
    else:
        # Пункт 3.2.2 прямо называет цементацию, но не нитроцементацию.
        hpmax, peak_h_formula = None, 'Требуется обоснование предельного контакта по п. 3.2.2'
    if 'testedPeakContact' in mat:
        if hpmax is not None:
            raise ValueError('Предел σHPmax уже определён по п. 3.2.2')
        hpmax = number(mat,'testedPeakContact')
        peak_h_formula = 'Предел σHPmax по испытаниям, указанным в паспорте (исходное данное)'
    yt = 1.
    if case_hardened or table == 17 or nitrided:
        compliant = flag(mat,'technologyCompliant')
        if case_hardened:
            core = number(mat,'coreHrc')
            compliant &= 30 <= core <= 45
        # Если в паспорте даны измерения, они имеют приоритет над общей отметкой.
        if 'caseDepth' in mat:
            depth = number(mat,'caseDepth')
            if table == 14:
                nominal = .28*module-.007*module**2
                bounds = (nominal-.2, nominal+.2)
            elif table == 15:
                bounds = (.13*module, min(.2*module,1.2))
            elif nitrided:
                bounds = (.07*module,.1*module) if row=='16.5' else (.1*module,.13*module)
            else:
                bounds = (.5*module,module) if row in ('17.5','17.6') else (.2*module,.4*module)
            compliant &= bounds[0] <= depth <= bounds[1]
        if 'grainSize' in mat and case_hardened:
            compliant &= number(mat,'grainSize') >= (5 if table==14 else 6)
        if 'noFerrite' in mat and table == 17:
            compliant &= flag(mat,'noFerrite')
        if 'nitridesAbsent' in mat and nitrided:
            compliant &= flag(mat,'nitridesAbsent')
        if not compliant:
            yt = .8 if nitrided else .70 if table == 17 and row not in ('17.5','17.6') else .75
        if case_hardened and not flag(mat,'smoothSpectrum'):
            raise ValueError('Табл. 14–15: для ударного спектра базовый предел изгиба требует испытаний')
        if table == 14:
            if module > 20:
                raise ValueError('Табл. 14, примечание: расчетная толщина слоя приведена для m≤20 мм')
            if row in ('14.1','14.2'):
                number(mat,'carbon',.75,1.1)
            elif row == '14.3':
                number(mat,'carbon',.6,1.4)
            if row == '14.2' and mat.get('highTemperProtected') is not None and flag(mat,'highTemperProtected'):
                flim = 950.  # Специальное условие состава и высокого отпуска, с. 44, прим. **.
        if table == 15:
            number(mat,'carbon',.7,1)
            number(mat,'nitrogen',.15,.3 if row=='15.1' else .5)
            if not flag(mat,'darkPhaseAbsent'):
                raise ValueError('Табл. 15 не допускает тёмную составляющую в диффузионном слое')
            if module > 8 and not flag(mat,'specialTests'):
                raise ValueError('При m>8 мм для нитроцементации укажите специальные испытания')
    grind = mat.get('grinding')
    if grind not in ('none','rough','finish'):
        raise ValueError('grinding: укажите none, rough или finish для переходной поверхности')
    ground = grind != 'none'
    yg = 1.
    if ground:
        if grinding is None:
            raise ValueError('Табл. 16: для шлифованной переходной поверхности азотированных зубьев Yg не задан')
        yg = grinding[0 if flag(mat,'goodGrinding') else 1]
    treatment = mat.get('rootTreatment')
    yd = 1.
    if treatment == 'peened' and peening:
        yd = number(mat,'YD',*peening[int(ground)])
    elif treatment != 'none':
        raise ValueError('Для этой строки выберите подтверждённую обработку корня: none или допустимый наклёп peened')
    if 'qF' in mat and (type(mat['qF']) is not int or mat['qF'] not in (6,9)):
        raise ValueError('qF: задайте 6 или 9 по результатам испытаний')
    q = 6 if homogeneous or ground or row in ('17.5','17.6','17.7') else 9 if nitrided or case_hardened else mat.get('qF')
    if mat.get('qF',q) != q:
        raise ValueError('qF противоречит обработке переходной поверхности, табл. 13.9')
    severe = flag(mat,'severeConsequences') if 'severeConsequences' in mat else False
    sh_min = (1.25 if homogeneous else 1.35) if severe else (1.1 if homogeneous else 1.2)
    sf = number(mat,'SF',sf_min) if 'SF' in mat else sf_min
    sh = number(mat,'SH',sh_min) if 'SH' in mat else sh_min
    fstatic, static_reason = _static_base(mat, row, hb, hrc, hv)
    # Для стали вне табл. 19 нужен отдельно назначенный коэффициент Sγ.
    fallback = flag(mat,'table19Inapplicable') if 'table19Inapplicable' in mat else False
    if fallback and fstatic is not None:
        raise ValueError('Паспорт одновременно указывает неприменимость и подходящую строку таблицы 19')
    ygst = 1.
    if ground:
        if bulk or row in ('17.5','17.6','17.7'):
            ygst = .95 if grind == 'rough' else 1.1
        elif case_hardened:
            ygst = (1.0 if grind == 'rough' else 1.05) if table == 14 else (.9 if grind == 'rough' else .95)
        else:
            fstatic, static_reason = None, 'Табл. 18 не задаёт YgSt для этой обработки и шлифованного корня'
    ydst = .95 if treatment == 'peened' and not ground else 1.
    gamma_a = .35 if normal else .1 if nitrided else .25 if hrc > 45 else None
    # Табл. 13.13 указывает 1,05 для химико-термической обработки только при
    # полировке до неё; для объёмной закалки отдельного значения не приведено.
    polish_yr = None
    if normal or row in ('17.5','17.6','17.7'):
        polish_yr = 1.2
    elif contour or (case_hardened or nitrided) and mat.get('polishedBeforeTreatment') is True:
        polish_yr = 1.05
    return dict(row=row,label=mat['label'],evidence=mat['evidence'],homogeneous=homogeneous,gammaA=gamma_a,
                polishedYR=polish_yr,YR=number(mat,'YR') if 'YR' in mat else None,
                flankRa=number(mat,'flankRa') if 'flankRa' in mat else None,
                hb=hb,hv=hv,qF=q,muF=number(mat,'muF',0,1) if 'muF' in mat else None,
                sigmaHlim=hlim,hFormula=hformula,sigmaFlimb0=flim,NHlim=min(120e6,30*hb**2.4),
                hpmax=hpmax,hPeakFormula=peak_h_formula,staticBase=fstatic,staticSource=static_reason,
                SH=sh,SF=sf,YZ=blank_factor[blank],YT=yt,Yg=yg,Yd=yd,YgSt=ygst,YdSt=ydst,
                deepContact=case_hardened or nitrided,staticFallback=fallback)


def _static_base(mat, row, hb, hrc, hv):
    """Табл. 19; отдельная проверка твёрдости и технологии для максимума."""
    unavailable = (None, 'Табл. 19 не содержит подтверждённой строки для этих условий')
    if row == '16.1':
        return (6.5*hb, 'табл. 19, нормализация и улучшение') if hb >= 200 else unavailable
    if row in ('16.2','16.3','16.4') and 48 <= hrc <= 52:
        kind = mat.get('peakRow')
        if row == '16.3' or row == '16.2' and kind == 'nickel':
            return 2500., 'табл. 19, объёмная закалка, Ni>1 %'
        if row == '16.4' or row == '16.2' and kind == 'other':
            return 2250., 'табл. 19, объёмная закалка, прочая сталь'
    if row == '16.6' and 24 <= mat['coreHrc'] <= 30:
        return 1800., 'табл. 19, азотирование, легированная сталь без алюминия'
    if row.startswith('14.') and 'peakRow' in mat:
        core = number(mat,'coreHrc')
        if mat['peakRow'] == 'reheatNickel' and (56<=hrc<=62 and 30<=core<=43 or 56<=hrc<=60 and 27<=core<=32):
            return 2800., 'табл. 19, цементация, повторный нагрев, Ni≥1 %'
        if mat['peakRow'] == 'directOther' and 54<=hrc<=60 and 30<=core<=43:
            return 2000., 'табл. 19, цементация, непосредственная закалка'
    if row.startswith('15.') and 56<=hrc<=60:
        core = number(mat,'coreHrc')
        if row == '15.1' and 32<=core<=45:
            return 2500., 'табл. 19, нитроцементация с автоматическим регулированием, сталь с Mo'
        if row == '15.2' and 27<=core<=45:
            return 2200., 'табл. 19, нитроцементация, прочая легированная сталь'
    if row in ('17.3','17.4') and 48<=hrc<=54 and 24<=mat['coreHrc']<=30:
        if row == '17.4' or mat.get('peakRow') == 'other':
            return 1800., 'табл. 19, контурная закалка, прочая легированная сталь'
        if mat.get('peakRow') == 'nickel':
            return 2200., 'табл. 19, контурная закалка, Ni>1 %'
    if row in ('17.5','17.6','17.7') and 48<=hrc<=52:
        if row == '17.7':
            return 1800., 'табл. 19, закалка ТВЧ до переходной поверхности'
        return (2500. if row=='17.5' else 2250.), 'табл. 19, сквозная закалка ТВЧ'
    return unavailable
