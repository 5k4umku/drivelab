import { fmt, statusLabel } from "./format.js";
export function makeReport(result, D, childrenOnly = false) {
  const {
    Document,
    Paragraph,
    TextRun,
    Table,
    TableRow,
    TableCell,
    HeadingLevel,
    WidthType,
    AlignmentType,
    PageNumber,
    Header,
    Footer,
    Math: Equation,
    MathRun,
    BorderStyle,
  } = D;
  const p = (text, options = {}) =>
    new Paragraph({
      children: [new TextRun({ text: String(text), ...options.run })],
      spacing: { after: 100 },
      ...options,
    });
  const heading = (text, level = HeadingLevel.HEADING_1) =>
    p(text, {
      heading: level,
      keepNext: true,
      spacing: { before: 240, after: 130 },
    });
  const math = (text) =>
    new Paragraph({
      children: [new Equation({ children: [new MathRun(text)] })],
      spacing: { after: 90 },
      keepNext: true,
    });
  const table = (headers, rows) =>
    new Table({
      width: { size: 100, type: WidthType.PERCENTAGE },
      columnWidths: headers.map(() => Math.floor(9500 / headers.length)),
      borders: Object.fromEntries(
        [
          "top",
          "bottom",
          "left",
          "right",
          "insideHorizontal",
          "insideVertical",
        ].map((k) => [
          k,
          { style: BorderStyle.SINGLE, size: 4, color: "C6CFD3" },
        ]),
      ),
      rows: [headers, ...rows].map(
        (row, index) =>
          new TableRow({
            tableHeader: index === 0,
            cantSplit: true,
            children: row.map(
              (value) =>
                new TableCell({
                  shading: index === 0 ? { fill: "EAF0ED" } : undefined,
                  margins: { top: 70, bottom: 70, left: 90, right: 90 },
                  children: [
                    p(value, {
                      spacing: { after: 20 },
                      run: { bold: index === 0, size: 19 },
                    }),
                  ],
                }),
            ),
          }),
      ),
    });
  const c = result.chosen,
    inp = result.input,
    children = [];
  const types = {
    spur: "Прямозубая",
    helical: "Косозубая",
    herringbone: "Шевронная",
  };
  children.push(
    p("Расчёт зубчатой передачи", { heading: HeadingLevel.TITLE }),
    p(`${types[inp.gearType]} передача внешнего зацепления`),
    p(inp.title, { run: { bold: true } }),
  );
  children.push(
    p(
      `Выбран модуль ${fmt(c.m)} мм, z₁ = ${c.z1}, z₂ = ${c.z2}, aw = ${fmt(result.a)} мм. Расчёт состоит из проектировочной части по семинарам и отдельной проверки по формулам ГОСТ 21354–87.`,
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
        ["ψbd", fmt(inp.psiBd), "Степень точности", "7"],
        ["αn, °", fmt(inp.alpha), "Смещения x₁; x₂", "0; 0"],
      ],
    ),
  );
  children.push(
    p(
      "Материал сохраняется по заданию. Для шестерни принят исходный класс Т1; для колеса — на две строки мягче по уточнению пользователя от 29.10.2026. Выбор другого класса требует проверки технологии термообработки.",
    ),
  );
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
      "Рекомендация соответствует минимальной ошибке передаточного числа среди взаимно простых пар. Числовая проверка прочности выполняется для выбранного варианта и может потребовать изменения размеров.",
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
        spacing: { before: 150, after: 80 },
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
        run: { bold: true },
        keepNext: true,
      }),
    );
    children.push(
      p(`Источник: ${s.source}`, { run: { size: 17, color: "61706B" } }),
    );
  }
  children.push(heading("Методика и ограничения"));
  children.push(
    p(
      "Семинарская часть воспроизводит последовательность бланка и коэффициенты Т1–Т9. Проверочная часть использует ГОСТ 21354–87 для наружного нулевого зацепления со стандартной рейкой 20° и улучшенными стальными колёсами. Коэффициенты распределения по ширине приняты по данным проекта; расчёт деформаций валов и опор в текущую модель не входит.",
    ),
  );
  children.push(
    p(
      "Для шевронной пары предполагаются симметричные половины, одинаковая нагрузка и равные встречные осевые силы. Проверяется одна половина с половиной суммарной ширины и нагрузки. Ширина центральной канавки в активную ширину не включается.",
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
      "DriveLab 0.1.0. Вычислительное ядро CPython. Для воспроизведения используйте сохранённый JSON проекта и эту версию исходного кода.",
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
  return new Document({
    creator: "DriveLab",
    title: "Расчёт зубчатой передачи",
    description:
      "Прослеживаемый расчёт по семинарам и проверка по формулам ГОСТ 21354–87",
    styles: {
      default: {
        document: {
          run: { font: "Times New Roman", size: 22, color: "000000" },
          paragraph: { spacing: { line: 260, after: 100 } },
        },
      },
      paragraphStyles: [
        {
          id: "Title",
          name: "Title",
          basedOn: "Normal",
          next: "Normal",
          run: {
            font: "Times New Roman",
            size: 36,
            bold: true,
            color: "000000",
          },
          paragraph: { spacing: { after: 220 } },
        },
        {
          id: "Heading1",
          name: "Heading 1",
          basedOn: "Normal",
          next: "Normal",
          run: {
            font: "Times New Roman",
            size: 28,
            bold: true,
            color: "000000",
          },
          paragraph: { keepNext: true, spacing: { before: 240, after: 130 } },
        },
      ],
    },
    sections: [
      {
        properties: {
          page: {
            size: { width: 11906, height: 16838 },
            margin: { top: 1000, bottom: 1000, left: 1250, right: 1050 },
          },
        },
        headers: {
          default: new Header({
            children: [
              p("DriveLab     Расчёт зубчатой передачи", {
                run: { size: 16, color: "728079" },
              }),
            ],
          }),
        },
        footers: {
          default: new Footer({
            children: [
              new Paragraph({
                alignment: AlignmentType.RIGHT,
                children: [
                  new TextRun({ text: "DriveLab 0.2.0   ·   ", size: 16 }),
                  new TextRun({ children: [PageNumber.CURRENT], size: 16 }),
                ],
              }),
            ],
          }),
        },
        children,
      },
    ],
  });
}

export function makeAssemblyReport(assembly, D) {
  const {
    Document,
    Paragraph,
    TextRun,
    Table,
    TableRow,
    TableCell,
    HeadingLevel,
    WidthType,
    Footer,
    PageNumber,
    Math: Equation,
    MathRun,
  } = D;
  const p = (text, options = {}) =>
    new Paragraph({
      children: [new TextRun(String(text))],
      spacing: { after: 120 },
      ...options,
    });
  const h = (text) =>
    p(text, {
      heading: HeadingLevel.HEADING_1,
      keepNext: true,
      spacing: { before: 260, after: 140 },
    });
  const table = (head, rows) =>
    new Table({
      width: { size: 100, type: WidthType.PERCENTAGE },
      columnWidths:
        head.length === 2
          ? [6100, 3700]
          : head.map(() => Math.floor(9800 / head.length)),
      borders: Object.fromEntries(
        [
          "top",
          "bottom",
          "left",
          "right",
          "insideHorizontal",
          "insideVertical",
        ].map((key) => [
          key,
          { style: D.BorderStyle.SINGLE, size: 4, color: "D9D9D9" },
        ]),
      ),
      rows: [head, ...rows].map(
        (row, i) =>
          new TableRow({
            tableHeader: i === 0,
            cantSplit: true,
            children: row.map(
              (text) =>
                new TableCell({
                  shading: i === 0 ? { fill: "E8EEF3" } : undefined,
                  margins: { top: 80, bottom: 80, left: 100, right: 100 },
                  verticalAlign: D.VerticalAlign.CENTER,
                  children: [
                    new Paragraph({
                      children: [
                        new TextRun({
                          text: String(text),
                          bold: i === 0,
                          size: 20,
                        }),
                      ],
                      spacing: { after: 20, line: 240 },
                    }),
                  ],
                }),
            ),
          }),
      ),
    });
  const children = [
    p("Расчёт цилиндрического редуктора", { heading: HeadingLevel.TITLE }),
    p(assembly.project.name),
    p(
      `DriveLab 0.2.0 · ${assembly.stages.length} ступеней · ${assembly.shafts.length} валов`,
    ),
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
      ],
    ),
    p(
      "Последовательные внешние зацепления, параллельные валы, нулевые смещения профиля. Номера подшипников, ресурс опор, прочность и упругая линия валов, шпонки и конструкция корпуса не рассчитаны. Габаритные проверки не заменяют рабочие чертежи.",
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
      new Paragraph({
        children: [new Equation({ children: [new MathRun(step.formula)] })],
        keepNext: true,
      }),
      p(step.detail),
    );
  children.push(
    h("Реакции опор и изгибающие моменты"),
    p(
      "На каждом валу две радиальные опоры и одна фиксирующая осевая. Силы приложены в полюсе зацепления: учитывается изгибающий момент от осевой силы на делительном радиусе. Расчёт для номинальной нагрузки; вес деталей, пуск и внешние нагрузки не включены. Знаки относятся к общей системе XYZ.",
    ),
  );
  children.push(
    new Paragraph({
      children: [
        new Equation({
          children: [new MathRun("ΣF = 0; ΣMx = 0; ΣMy = 0; M = r × F")],
        }),
      ],
    }),
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
    children.push(
      p(`Ступень ${stage.index + 1}. Полный расчёт`, {
        heading: HeadingLevel.HEADING_1,
        pageBreakBefore: true,
      }),
    );
    children.push(...makeReport(stage.result, D, true));
  }
  return new Document({
    creator: "DriveLab",
    title: assembly.project.name,
    styles: {
      default: {
        document: {
          run: { font: "Times New Roman", size: 22, color: "000000" },
          paragraph: { spacing: { line: 260, after: 100 } },
        },
      },
      paragraphStyles: [
        {
          id: "Title",
          name: "Title",
          basedOn: "Normal",
          next: "Normal",
          run: {
            font: "Times New Roman",
            size: 36,
            bold: true,
            color: "000000",
          },
          paragraph: { spacing: { after: 220 } },
        },
        {
          id: "Heading1",
          name: "Heading 1",
          basedOn: "Normal",
          next: "Normal",
          run: {
            font: "Times New Roman",
            size: 28,
            bold: true,
            color: "000000",
          },
          paragraph: { keepNext: true, spacing: { before: 240, after: 130 } },
        },
      ],
    },
    sections: [
      {
        properties: {
          page: {
            size: { width: 11906, height: 16838 },
            margin: { top: 1000, bottom: 1000, left: 1100, right: 1000 },
          },
        },
        footers: {
          default: new Footer({
            children: [
              new Paragraph({
                children: [
                  new TextRun("DriveLab 0.2.0 · "),
                  new TextRun({ children: [PageNumber.CURRENT] }),
                ],
              }),
            ],
          }),
        },
        children,
      },
    ],
  });
}
