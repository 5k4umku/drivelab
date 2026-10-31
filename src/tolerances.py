"""ГОСТ 25346–2013, табл.1: стандартные допуски IT5…IT12, 0<d≤500 мм.

Только ширина допуска и поля H/h. Это не нормы точности зубчатого венца
и не автоматическое назначение посадки подшипника или неподвижного колеса.
"""
import math
ROWS=(
    (3,4,6,10,14,25,40,60,100), (6,5,8,12,18,30,48,75,120),
    (10,6,9,15,22,36,58,90,150), (18,8,11,18,27,43,70,110,180),
    (30,9,13,21,33,52,84,130,210), (50,11,16,25,39,62,100,160,250),
    (80,13,19,30,46,74,120,190,300), (120,15,22,35,54,87,140,220,350),
    (180,18,25,40,63,100,160,250,400), (250,20,29,46,72,115,185,290,460),
    (315,23,32,52,81,130,210,320,520), (400,25,36,57,89,140,230,360,570),
    (500,27,40,63,97,155,250,400,630),
)
SOURCE='https://files.stroyinf.ru/Data2/1/4293773/4293773435.pdf#page=16'


def tolerance(diameter,grade):
    if isinstance(diameter,bool) or not isinstance(diameter,(int,float)) or not math.isfinite(diameter) or not 0<diameter<=500:
        raise ValueError('Диаметр для таблицы IT: 0<d≤500 мм.')
    if isinstance(grade,bool) or not isinstance(grade,int) or not 5<=grade<=12:
        raise ValueError('Реализованы квалитеты IT5…IT12.')
    row=next(r for r in ROWS if diameter<=r[0])
    return row[grade-4]


def fit(diameter=30,hole_grade=7,shaft_grade=6):
    hole,shaft=tolerance(diameter,hole_grade),tolerance(diameter,shaft_grade)
    return dict(diameter=diameter,holeGrade=hole_grade,shaftGrade=shaft_grade,
        holeTolerance=hole,shaftTolerance=shaft,holeMin=diameter,holeMax=diameter+hole/1000,
        shaftMin=diameter-shaft/1000,shaftMax=diameter,gapMin=0,gapMax=(hole+shaft)/1000,
        source=SOURCE,rows=[dict(grade=g,microns=tolerance(diameter,g)) for g in range(5,13)],
        note='H/h: зазор от нуля. Посадка показана для изучения допусков; закрепление колеса и посадки подшипников требуют отдельного обоснования.')
