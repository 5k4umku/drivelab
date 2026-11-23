const pages = [
  "Обложка, исходные данные, материалы и таблица напряжений",
  "Пиковый изгиб, варианты и результаты проверок",
  "Условия применимости, коэффициенты и геометрия по чертежу",
  "Рабочее межосевое расстояние и начало проверки по ГОСТ",
  "Перекрытие зубьев и удельная нагрузка",
  "Эквивалентное число зубьев и динамические коэффициенты",
  "Распределение нагрузки и коэффициенты для максимума",
  "Коэффициенты контакта и контактное напряжение",
  "Контактная выносливость и число циклов",
  "Предел изгиба шестерни и допускаемые напряжения",
  "Условия смазки и изгиб шестерни",
  "Предел изгиба колеса и допускаемые напряжения",
  "Условия смазки и изгиб колеса",
  "Пиковые нагрузки, методика и ограничения",
  "Ограничения, источники и принятые коэффициенты",
];

export function mountReportReader(tour, options) {
  const trigger = tour.querySelector("button[data-feature-docx]");
  const reader = tour.querySelector("[data-feature-report-reader]");
  if (!trigger || !reader) return { open() {}, cleanup() {} };
  trigger.setAttribute("aria-expanded", "false");
  let closedByUser = false;

  function render() {
    reader.innerHTML = `
      <div class="feature-reader-toolbar">
        <h3>Демонстрационный отчёт DriveLab</h3>
        <div class="feature-reader-controls">
          <label>Страница <select aria-label="Страница отчёта"></select></label>
          <button type="button" data-reader-zoom aria-pressed="false">Увеличить</button>
          <button type="button" data-reader-close>Закрыть</button>
        </div>
      </div>`;
    const toolbar = reader.querySelector(".feature-reader-toolbar");
    const select = toolbar.querySelector("select");
    const zoom = toolbar.querySelector("[data-reader-zoom]");
    const figures = pages.map((description, index) => {
      const number = index + 1;
      const figure = document.createElement("figure");
      const caption = document.createElement("figcaption");
      const image = new Image(869, 1228);
      const viewport = document.createElement("div");
      viewport.className = "feature-reader-page";
      viewport.setAttribute("role", "group");
      viewport.setAttribute("aria-label", "Страница " + number + " · " + description);
      image.loading = "lazy";
      image.decoding = "async";
      image.alt = description;
      image.src = new URL("./presentation-report/gost-annex-11-" + String(number).padStart(2, "0") + ".png", import.meta.url);
      caption.textContent = "Страница " + number + " из " + pages.length + " · " + description;
      viewport.append(image);
      figure.append(caption, viewport);
      select.add(new Option(String(number) + " из " + pages.length, String(index)));
      return figure;
    });
    reader.append(...figures);

    select.addEventListener("change", () => {
      const figure = figures[Number(select.value)];
      reader.scrollTop += figure.getBoundingClientRect().top - toolbar.getBoundingClientRect().bottom;
    }, options);
    reader.addEventListener("scroll", () => {
      const marker = toolbar.getBoundingClientRect().bottom + 12;
      const atEnd = reader.scrollHeight - reader.scrollTop - reader.clientHeight < 2;
      const index = atEnd ? figures.length - 1 : figures.findIndex(figure => figure.getBoundingClientRect().bottom > marker);
      if (index >= 0) select.selectedIndex = index;
    }, { ...options, passive: true });
    zoom.addEventListener("click", () => {
      const current = figures[select.selectedIndex];
      const top = current.getBoundingClientRect().top;
      const enlarged = reader.toggleAttribute("data-report-enlarged");
      zoom.setAttribute("aria-pressed", String(enlarged));
      for (const viewport of reader.querySelectorAll(".feature-reader-page")) {
        if (enlarged) viewport.tabIndex = 0;
        else viewport.removeAttribute("tabindex");
      }
      reader.scrollTop += current.getBoundingClientRect().top - top;
    }, options);
    toolbar.querySelector("[data-reader-close]").addEventListener("click", () => {
      closedByUser = true;
      reader.hidden = true;
      trigger.setAttribute("aria-expanded", "false");
      trigger.focus();
    }, options);
  }

  function open() {
    if (!reader.hasChildNodes()) render();
    reader.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
  }

  trigger.addEventListener("click", () => {
    open();
    reader.scrollIntoView({ block: "start", behavior: "instant" });
    reader.focus({ preventScroll: true });
  }, options);

  return {
    open() {
      if (!closedByUser) open();
    },
    cleanup() {
      reader.hidden = true;
      reader.replaceChildren();
      reader.removeAttribute("data-report-enlarged");
      trigger.removeAttribute("aria-expanded");
    },
  };
}

