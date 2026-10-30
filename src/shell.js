// Навигация и оформление не меняют инженерные данные проекта.
export function setupShell() {
  const labels = {
    constructor: "Компоновка",
    overview: "Ступень",
    selection: "Подбор",
    variants: "Варианты",
    checks: "Проверки",
    coefficients: "Коэффициенты",
    calculation: "Ход расчёта",
    method: "Методика",
  };
  const select = document.querySelector("#theme-select");
  function theme(value) {
    document.documentElement.dataset.theme =
      value === "system"
        ? matchMedia("(prefers-color-scheme: dark)").matches
          ? "dark"
          : "light"
        : value;
    try {
      localStorage.setItem("drivelab-theme", value);
    } catch {}
    document.querySelector('meta[name="theme-color"]').content =
      document.documentElement.dataset.theme === "dark" ? "#0d141e" : "#f1f4f8";
    document.dispatchEvent(new CustomEvent("drivelab-theme"));
  }
  let preference = "system";
  try {
    preference = localStorage.getItem("drivelab-theme") || "system";
  } catch {}
  if (!["system", "light", "dark"].includes(preference)) preference = "system";
  select.value = preference;
  theme(preference);
  select.onchange = () => theme(select.value);
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (select.value === "system") theme("system");
  });
  const menu = document.querySelector("#mobile-menu");
  const narrow = matchMedia("(max-width: 800px)"),
    sidebar = document.querySelector(".sidebar");
  function syncMenu() {
    sidebar.inert =
      narrow.matches && !document.body.classList.contains("menu-open");
  }
  narrow.addEventListener("change", syncMenu);
  menu.onclick = () => {
    const open = document.body.classList.toggle("menu-open");
    menu.setAttribute("aria-expanded", String(open));
    syncMenu();
  };
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      document.body.classList.remove("menu-open");
      menu.setAttribute("aria-expanded", "false");
      syncMenu();
    }
  });
  function route() {
    const id = Object.hasOwn(labels, location.hash.slice(1))
      ? location.hash.slice(1)
      : "constructor";
    for (const page of document.querySelectorAll(".page-section"))
      page.hidden = page.id !== id;
    for (const link of document.querySelectorAll(
      ".sidebar nav a,.mobile-nav a",
    )) {
      link.classList.toggle("active", link.hash === "#" + id);
      if (link.hash === "#" + id) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    }
    document.querySelector("#route-title").textContent = labels[id];
    document.body.classList.remove("menu-open");
    menu.setAttribute("aria-expanded", "false");
    syncMenu();
    document.body.dataset.page = id;
    window.scrollTo({ top: 0, behavior: "instant" });
    requestAnimationFrame(() => window.dispatchEvent(new Event("resize")));
  }
  addEventListener("hashchange", route);
  route();
  new MutationObserver(() => {
    const id = document.body.dataset.page;
    document
      .querySelectorAll(".page-section")
      .forEach((p) => (p.hidden = p.id !== id));
  }).observe(document.querySelector("main"), { childList: true });
  // Обе сцены используют одни данные. На небольшом экране выбираем нужный вид.
  const root = document.querySelector("#constructor"),
    scene = root.querySelector(".assembly-scene"),
    scheme = root.querySelector(".schematic-editor");
  const studio = document.createElement("div");
  studio.className = "studio";
  scene.before(studio);
  studio.innerHTML =
    '<div class="studio-heading"><div><span class="live-dot"></span> Модель редуктора</div><div class="tool-tabs"><button data-scene="3d" class="active">Объёмная модель</button><button data-scene="2d">Схема 2D</button></div></div>';
  studio.append(scene, scheme);
  scheme.hidden = true;
  studio.querySelectorAll("[data-scene]").forEach(
    (b) =>
      (b.onclick = () => {
        scene.hidden = b.dataset.scene !== "3d";
        scheme.hidden = b.dataset.scene !== "2d";
        studio
          .querySelectorAll("[data-scene]")
          .forEach((x) => x.classList.toggle("active", x === b));
      }),
  );
  // Модель первой: исходные поля остаются доступными, но не заслоняют результат.
  root.querySelector(".builder-toolbar").after(studio);
  const setup = document.createElement("details");
  setup.className = "project-setup";
  setup.open = false;
  setup.innerHTML =
    "<summary><span>01</span><b>Исходные данные и двигатель</b><small>Мощность, частота, корпус</small></summary>";
  studio.after(setup);
  const global = root.querySelector("#builder-global"),
    motor = root.querySelector(".motor-card");
  setup.append(global);
  if (motor) setup.append(motor.parentElement);
  const hint = document.createElement("div");
  hint.className = "workflow-hint";
  hint.innerHTML =
    '<span>01 <b>Соберите схему</b></span><i>→</i><a href="#selection">02 <b>Подберите параметры</b></a><i>→</i><a href="#checks">03 <b>Проверьте и сохраните</b></a>';
  root.querySelector(".page-heading").after(hint);
}
