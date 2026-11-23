import { fmt, statusLabel } from "./format.js";
import { siteVersion } from "./version.js";

const ink = "171B21";
const accent = "FFB277";
const muted = "515B63";
const paperWidth = 9746; // A4 less two 1080-twip margins.

function reportLayout(D) {
  const p = (text, { run, ...options } = {}) => new D.Paragraph({
    children: [new D.TextRun({ text: String(text), ...run })],
    ...options,
  });
  const heading = (text) => p(text, {
    heading: D.HeadingLevel.HEADING_1,
    keepNext: true,
    shading: { fill: ink },
    border: { left: { style: D.BorderStyle.SINGLE, color: accent, size: 24, space: 8 } },
    spacing: { before: 180, after: 90, line: 350 },
    run: { color: "FFFFFF", size: 25, bold: true },
  });
  const math = (text) => new D.Paragraph({
    children: [new D.Math({ children: [new D.MathRun(text)] })],
    keepNext: true,
    spacing: { after: 48 },
  });
  function table(headers, rows, shares = headers.map(() => 1)) {
    const total = shares.reduce((sum, value) => sum + value, 0);
    const widths = shares.map(value => Math.floor(paperWidth * value / total));
    widths[widths.length - 1] += paperWidth - widths.reduce((sum, width) => sum + width, 0);
    const edge = { style: D.BorderStyle.SINGLE, size: 4, color: "D9D9D9" };
    return new D.Table({
      width: { size: paperWidth, type: D.WidthType.DXA },
      layout: D.TableLayoutType.FIXED,
      columnWidths: widths,
      borders: { top: edge, bottom: edge, left: edge, right: edge, insideHorizontal: edge, insideVertical: edge },
      rows: [headers, ...rows].map((row, i) => new D.TableRow({
        tableHeader: i === 0,
        cantSplit: true,
        children: row.map((value, j) => new D.TableCell({
          width: { size: widths[j], type: D.WidthType.DXA },
          shading: { fill: i === 0 ? "333C46" : i % 2 ? "FFFFFF" : "F4F5F5" },
          margins: { top: 48, bottom: 48, left: 95, right: 95 },
          verticalAlign: D.VerticalAlign.CENTER,
          children: [p(value, {
            spacing: { after: 0, line: 226 },
            alignment: i && /^[−+–-]?[\d—][\d\s,.−+–/%°-]*$/u.test(String(value)) ? D.AlignmentType.RIGHT : D.AlignmentType.LEFT,
            run: { bold: i === 0, color: i === 0 ? "FFFFFF" : ink, size: 19 },
          })],
        })),
      })),
    });
  }
  function cover(kind, title, subtitle, pageBreakBefore = false) {
    const noEdge = { style: D.BorderStyle.NIL };
    const panel = new D.Table({
      width: { size: paperWidth, type: D.WidthType.DXA },
      columnWidths: [paperWidth],
      borders: { top: noEdge, bottom: noEdge, left: noEdge, right: noEdge },
      rows: [new D.TableRow({ cantSplit: true, children: [new D.TableCell({
        shading: { fill: ink },
        margins: { top: 175, bottom: 175, left: 245, right: 245 },
        children: [
          p("DriveLab   /   " + siteVersion, {
            spacing: { after: 85 }, run: { size: 23, color: accent, bold: true },
          }),
          p(kind, {
            heading: D.HeadingLevel.TITLE, spacing: { before: 0, after: 55, line: 260 },
            run: { size: 38, color: "FFFFFF", bold: true },
          }),
          p(title, { spacing: { after: 0 }, run: { size: 22, color: "E6E8EB" } }),
        ],
      })] })],
    });
    return [
      ...(pageBreakBefore ? [new D.Paragraph({
        pageBreakBefore: true, keepNext: true, spacing: { after: 0, line: 20, lineRule: "exact" },
      })] : []),
      panel,
      p(subtitle, { run: { color: muted, bold: true, size: 20 }, spacing: { before: 110, after: 110 }, keepNext: true }),
    ];
  }
  function document(title, kind, children) {
    const footer = new D.Paragraph({
      alignment: D.AlignmentType.RIGHT,
      children: [
        new D.TextRun({ text: "DriveLab " + siteVersion + "     /     ", color: muted, size: 17 }),
        new D.TextRun({ children: [D.PageNumber.CURRENT], bold: true, size: 18 }),
        new D.TextRun({ text: " из ", color: muted, size: 17 }),
        new D.TextRun({ children: [D.PageNumber.TOTAL_PAGES], size: 17 }),
      ],
    });
    return new D.Document({
      creator: "DriveLab", title, description: kind,
      styles: { default: { document: {
        run: { font: "Calibri", size: 21, color: ink },
        paragraph: { spacing: { line: 250, after: 84 }, widowControl: true },
      } } },
      sections: [{
        properties: { page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 940, bottom: 960, left: 1080, right: 1080, header: 450, footer: 450 },
        } },
        headers: { default: new D.Header({ children: [p("DriveLab     /     " + kind, { run: { size: 17, color: muted } })] }) },
        footers: { default: new D.Footer({ children: [footer] }) },
        children,
      }],
    });
  }
  return { p, heading, math, table, cover, document };
}

export function makeReport(result, D, childrenOnly = false) {
  const { p, heading, math, table, cover, document } = reportLayout(D);
  const c = result.chosen,
    inp = result.input,
    children = [];
  const types = {
    spur: "Прямозубая",
    helical: "Косозубая",
    herringbone: "Шевронная",
  };
  const description = `${types[inp.gearType]} передача ${inp.meshType === "internal" ? "внутреннего" : "внешнего"} зацепления`;
  const kind = "Расчёт зубчатой передачи";
  if (childrenOnly) children.push(p(inp.title, { run: { bold: true } }), p(description));
  else children.push(...cover(kind, inp.title, description));
  children.push(
    p(
      inp.meshType === "internal"
        ? "Заданная геометрия по ГОСТ 19274–73, табл.2, x₁=x₂=0. Прочность внутреннего зацепления, полная интерференция и способ сборки не подтверждены."
        : inp.geometryMode === "given" ? `Размеры по чертежу: mn = ${fmt(c.m)} мм, z₁/z₂ = ${c.z1}/${c.z2}, aw = ${fmt(result.a)} мм.` : `Выбран модуль ${fmt(c.m)} мм, z₁ = ${c.z1}, z₂ = ${c.z2}, aw = ${fmt(result.a)} мм. Расчёт состоит из проектировочной части по семинарам и отдельной проверки по формулам ГОСТ 21354–87.`,
    ),
  );
  const failures = result.checks.filter((x) => x.status === "fail"),
    pending = result.checks.filter((x) => x.status === "pending");
  children.push(
    p(
      `Статус: ${failures.length ? "есть невыполненные условия" : pending.length ? "требуется уточнение условий применимости" : "проверки принятой модели выполнены"}. Невыполненных условий: ${failures.length}; требуют уточнения: ${pending.length}.`,
      { run: { bold: true } },
    ),
  );
  children.push(
    p(
      "Шестерня — индекс 1, колесо — индекс 2. Промежуточные значения вычисляются без округления; отображаемые подстановки округлены до шести знаков. Нормальный модуль обозначается mn.",
    ),
  );
  children.push(heading("Исходные данные"));
  children.push(
    table(
      ["Параметр", "Значение", "Параметр", "Значение"],
      [
        ["P₁, кВт", fmt(inp.power), "n₁, мин⁻¹", fmt(inp.speed)],
        ["u", fmt(inp.ratio), "η", fmt(inp.efficiency)],
        ["Ресурс, ч", fmt(inp.life), "KA", fmt(inp.KA)],
        [
          "Kп",
          fmt(inp.startup),
          "Количество пусков",
          inp.peakCount ? String(inp.peakCount) : "Не задано",
        ],
        ["Материал 1", inp.material1, "Материал 2", inp.material2],
        ["Класс 1", inp.rowName1, "Класс 2", inp.rowName2],
        [
          "HB₁",
          `${inp.hb1min}–${inp.hb1max}`,
          "HB₂",
          `${inp.hb2min}–${inp.hb2max}`,
        ],
        ["σHlim₁, МПа", fmt(inp.sigmaH1), "σHlim₂, МПа", fmt(inp.sigmaH2)],
        ["σFlim₁, МПа", fmt(inp.sigmaF1), "σFlim₂, МПа", fmt(inp.sigmaF2)],
        ["ψbd", fmt(inp.psiBd), "Степень точности", String(inp.accuracy)],
        ["αn, °", fmt(inp.alpha), "Смещения x₁; x₂", `${fmt(inp.x1 ?? 0)}; ${fmt(inp.x2 ?? 0)}`],
      ],
    ),
  );
  children.push(
    p(
      inp.gost?.materials
        ? "Свойства материалов для проверки прочности заданы паспортами венцов."
        : inp.materialMode === "custom"
        ? `Пользовательские свойства материала. Источник: ${inp.materialSource}. Правило двух строк таблицы требует отдельного подтверждения.`
        : "Для шестерни принят выбранный класс Т1; для колеса — на две строки мягче. Марки сталей задаются независимо; достижимость свойств проверяется по технологии и размеру заготовки.",
    ),
  );
  if (Array.isArray(inp.gost?.materials) && inp.gost.materials.every(x => x && typeof x === "object")) {
    children.push(heading("Паспорта материалов для проверки прочности"));
    const passport = result.rating?.materialProperties;
    children.push(table(["Венец и обработка","Строка ГОСТ","HB / HV / HRCэ","Источник"], inp.gost.materials.map((x,i)=>[
      x.label, String(x.row), [x.hb,x.hv,x.hrc].map(v=>fmt(v)).join(" / "), x.evidence
    ]), [25, 15, 23, 37]));
    if (passport) children.push(table(["Венец","σHlim, МПа","σFlimb⁰, МПа","SH / SF"],passport.map((x,i)=>[i?"Колесо":"Шестерня",fmt(x.sigmaHlim),fmt(x.sigmaFlimb0),fmt(x.SH)+" / "+fmt(x.SF)])));
  }
  if (inp.gost?.basic) children.push(p("Общие зависимости ГОСТ. Основание для коэффициентов: "+inp.gost.basic.source));
  if (Array.isArray(inp.gost?.spectrum) && inp.gost.spectrum.every(s => s && typeof s === "object")) {
    children.push(heading("Циклограмма за расчётный ресурс"),table(["Ступень","Ti / Tном","Время, %","ni / nном"],inp.gost.spectrum.map((s,i)=>[i+1,fmt(s.torqueRatio),fmt(100*s.timeFraction),fmt(s.speedRatio ?? 1)])));
  }
  const rating = result.rating;
  children.push(heading("Напряжения и допускаемые значения"));
  if (rating?.available) {
    children.push(table(["Проверка", "Напряжение, МПа", "Допускаемое, МПа"], [
      ["Контакт", rating.h, rating.hAllow],
      ["Изгиб шестерни", rating.fs?.[0], rating.fAllow?.[0]],
      ["Изгиб колеса", rating.fs?.[1], rating.fAllow?.[1]],
      ["Пиковый контакт", rating.hmax, rating.hMaxAllow],
      ["Пиковый изгиб шестерни", rating.fsmax?.[0], rating.fMaxAllow?.[0]],
      ["Пиковый изгиб колеса", rating.fsmax?.[1], rating.fMaxAllow?.[1]],
    ].map(([label, stress, limit]) => [label, fmt(stress, 3), fmt(limit, 3)]), [42, 29, 29]));
  } else {
    children.push(p(rating?.reason || "Для этой ступени проверка прочности недоступна."));
  }
  children.push(heading("Сравнение вариантов"));
  children.push(
    table(
      ["mn, мм", "z₁ / z₂", "uф", "δu, %", "β, °", "Fa, Н"],
      result.variants.map((v) => [
        fmt(v.m),
        `${v.z1} / ${v.z2}`,
        fmt(v.u, 6),
        fmt(v.errorPct, 4),
        fmt(v.beta),
        fmt(v.Fa),
      ]),
    ),
  );
  children.push(
    p(
      inp.meshType === "internal"
        ? "Размеры внутренней пары заданы пользователем. Здесь показан один вариант без автоматического подбора по прочности."
        : inp.geometryMode === "given" ? "Геометрия задана по чертежу. Проверка использует рабочие диаметры и фактические смещения." : "Рекомендация соответствует минимальной ошибке передаточного числа среди взаимно простых пар. Числовая проверка прочности выполняется для выбранного варианта и может потребовать изменения размеров.",
    ),
  );
  children.push(heading("Результаты проверок"));
  for (const check of result.checks) {
    children.push(
      p(`${statusLabel[check.status]}. ${check.title}`, {
        run: { bold: true },
        keepNext: true,
      }),
      p(check.detail),
    );
  }
  let section = "";
  for (const s of result.trace) {
    if (s.section !== section) {
      section = s.section;
      children.push(heading(section.replace(/^\d+\.\s*/, "")));
    }
    children.push(
      p(s.title, {
        run: { bold: true },
        keepNext: true,
        spacing: { before: 110, after: 44 },
      }),
    );
    children.push(math(s.formula));
    children.push(
      p(s.substitution, {
        run: { size: 19, font: "Cambria Math" },
        keepNext: true,
      }),
    );
    children.push(
      p(`Результат: ${fmt(s.value, 6)} ${s.unit}`, {
        run: { bold: true, color: "834119" },
        keepNext: true,
      }),
    );
    children.push(
      p(`Источник: ${s.source}`, { run: { size: 18, color: muted } }),
    );
  }
  children.push(heading("Методика и ограничения"));
  children.push(
    p(
      "Семинарская часть воспроизводит последовательность бланка и коэффициенты Т1–Т9. Проверочная часть использует ГОСТ 21354–87 для наружного зацепления с исходным контуром 20°. Геометрия, паспорт материала, режим нагрузки и дополнительные условия определяют применимые ветви проверки. Коэффициенты распределения по ширине приняты по данным проекта; расчёт деформаций валов и опор в текущую модель не входит.",
    ),
  );
  children.push(
    p(
      "Для шевронной пары проверяется более нагруженная половина. Заданная доля момента определяет встречные осевые силы. Ширина центральной канавки в активную ширину не включается.",
    ),
  );
  children.push(
    p(
      "Условия, отмеченные как требующие уточнения, не считаются выполненными. Отношение допускаемого напряжения к расчётному — коэффициент использования допускаемого запаса, а не замена нормативного SH или SF.",
    ),
  );
  children.push(
    p(
      "ГОСТ 21354–87: https://protect.gost.ru/gost/details/01aeced3-5fa6-4ed4-becc-02dbddd25624",
    ),
  );
  children.push(
    p(
      "Текст стандарта: https://files.stroyinf.ru/Data2/1/4294832/4294832225.pdf",
    ),
  );
  children.push(
    p(
      "DriveLab " + siteVersion + ". Вычислительное ядро CPython. Для воспроизведения используйте сохранённый JSON проекта и эту версию исходного кода.",
    ),
  );
  children.push(heading("Принятые коэффициенты"));
  const keys = [
    "KHbeta",
    "KFbeta",
    "g0",
    "fpb1",
    "fpb2",
    "deltaH",
    "deltaF",
    "muH",
    "muF",
    "mH",
    "mF",
    "NFG",
    "NHG1",
    "NHG2",
    "ZR",
    "ZVZL",
    "YA",
    "YR",
    "YzSmall",
    "YzLarge",
    "SH",
    "SF",
  ];
  children.push(
    table(
      ["Коэффициент", "Значение"],
      keys.map((key) => [key, fmt(inp[key], 6)]),
    ),
  );
  if (childrenOnly) return children;
  return document(inp.title, kind, children);
}

export function makeAssemblyReport(assembly, D) {
  const { p, heading: h, math, table, cover, document } = reportLayout(D);
  const kind = "Расчёт цилиндрического редуктора";
  const children = [
    ...cover(kind, assembly.project.name, "Ступени: " + assembly.stages.length + "   /   Валы: " + assembly.shafts.length),
    h("Итоговые параметры"),
    table(
      ["Параметр", "Значение"],
      [
        ["Мощность на входе, кВт", fmt(assembly.project.power)],
        ["Частота на входе, мин⁻¹", fmt(assembly.project.speed)],
        ["Общее фактическое передаточное число", fmt(assembly.totalRatio, 6)],
        ["Общий КПД", fmt(assembly.efficiency, 6)],
        ["Мощность на выходе, кВт", fmt(assembly.outputPower, 6)],
        ["Частота на выходе, мин⁻¹", fmt(assembly.outputSpeed, 6)],
        ["Момент на выходе, Н·м", fmt(assembly.outputTorque, 6)],
        ["Потери мощности, кВт", fmt(assembly.lostPower, 6)],
      ], [63, 37],
    ),
    p(
      "Последовательные цилиндрические зацепления, параллельные валы, смещения профиля указаны для каждой ступени. Номера подшипников, ресурс опор, прочность и упругая линия валов, шпонки и конструкция корпуса не рассчитаны. Габаритные проверки не заменяют рабочие чертежи.",
    ),
    h("Поток мощности и компоновка"),
    table(
      ["Ступень", "Тип зубьев", "uф", "Z, мм", "Направление XY, °"],
      assembly.stages.map((s) => [
        String(s.index + 1),
        { spur: "Прямые", helical: "Косые", herringbone: "Шеврон" }[
          s.result.input.gearType
        ],
        fmt(s.result.chosen.u, 6),
        fmt(s.axial),
        fmt(s.angle),
      ]),
    ),
  ];
  for (const step of assembly.trace)
    children.push(
      p(step.title, { keepNext: true }),
      math(step.formula),
      p(step.detail),
    );
  children.push(
    h("Реакции опор и изгибающие моменты"),
    p(
      "На каждом валу две радиальные опоры и одна фиксирующая осевая. Силы приложены в полюсе зацепления: учитывается изгибающий момент от осевой силы на делительном радиусе. Расчёт для номинальной нагрузки; вес деталей, пуск и внешние нагрузки не включены. Знаки относятся к общей системе XYZ.",
    ),
  );
  children.push(
    math("ΣF = 0; ΣMx = 0; ΣMy = 0; M = r × F"),
  );
  for (const shaft of assembly.shafts) {
    children.push(
      h(`Вал ${shaft.index + 1}`),
      p(
        `Диаметр для компоновки ${fmt(shaft.diameter)} мм; частота со знаком ${fmt(shaft.signedSpeed)} мин⁻¹; момент ${fmt(shaft.torque)} Н·м. Фиксирующая опора ${shaft.locating}.`,
      ),
      table(
        ["Опора", "Z, мм", "Rx, Н", "Ry, Н", "Rz, Н", "Rrad, Н"],
        ["A", "B"].map((k) => [
          k,
          fmt(shaft[k].z, 2),
          ...shaft[k].vector.map((v) => fmt(v, 2)),
          fmt(shaft[k].radial, 2),
        ]),
      ),
      p(
        `Максимальный суммарный изгибающий момент: ${fmt(shaft.maxBending, 4)} Н·м.`,
      ),
      table(
        ["Сечение Z, мм", "Сторона", "Mx, Н·м", "My, Н·м", "M, Н·м"],
        shaft.diagram.map((v) => [
          fmt(v.z, 2),
          v.side === "left" ? "Слева" : "Справа",
          fmt(v.Mx, 3),
          fmt(v.My, 3),
          fmt(v.M, 3),
        ]),
      ),
    );
  }
  children.push(h("Проверки компоновки"));
  for (const c of assembly.checks)
    children.push(
      p(`${statusLabel[c.status]} · ${c.title}`, { keepNext: true }),
      p(c.detail),
    );
  children.push(
    h("Основания расчёта"),
    p(
      "ГОСТ 21354–87: прочность цилиндрических эвольвентных колёс внешнего зацепления. Область реализованного профиля указана в отчёте каждой ступени.",
    ),
    p(
      "Статика опор: равновесие сил и моментов твёрдого тела. OpenStax, University Physics, §12.1: https://openstax.org/books/university-physics-volume-1/pages/12-1-conditions-for-static-equilibrium",
    ),
    p(
      "Коэффициенты KHβ и KFβ задаются для каждой ступени. Изменение опор сбрасывает подтверждение их применимости; статические реакции сами по себе не определяют эти коэффициенты.",
    ),
  );
  for (const stage of assembly.stages) {
    children.push(...cover("Ступень " + (stage.index + 1) + ". Полный расчёт", assembly.project.name, "Расчёт зубчатой передачи", true));
    children.push(...makeReport(stage.result, D, true));
  }
  return document(assembly.project.name, kind, children);
}
