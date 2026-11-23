const intro = document.querySelector("#product-intro");
const workbench = document.querySelector("#workbench");
const workbenchRoutes = new Set([
  "#main", "#constructor", "#assembly-checks", "#overview", "#selection",
  "#variants", "#checks", "#coefficients", "#calculation", "#method",
]);

const colorScheme = matchMedia("(prefers-color-scheme: dark)");
function applyInitialTheme() {
  let preference;
  try {
    preference = localStorage.getItem("drivelab-theme");
  } catch {}
  const theme = preference === "dark" || preference === "light"
    ? preference
    : colorScheme.matches ? "dark" : "light";
  document.documentElement.dataset.theme = theme;
  const color = document.querySelector('meta[name="theme-color"]');
  if (color) color.content = theme === "dark" ? "#0d141e" : "#f1f4f8";
}

let currentScreen;
let workbenchImport;
let presentationImport;
let cleanupPresentation;
let cleanupFeatureTour;
let revision = 0;

function focusScreen(root) {
  if (!root.hasAttribute("tabindex")) root.tabIndex = -1;
  root.focus({ preventScroll: true });
}

async function enterPresentation(version) {
  try {
    presentationImport ??= import("./presentation-scene.js");
    const { mountPresentation } = await presentationImport;
    if (version !== revision) return;
    const cleanup = mountPresentation(intro);
    if (version === revision) cleanupPresentation = cleanup;
    else cleanup?.();
  } catch (error) {
    if (version === revision) {
      if (intro.dataset.presentationState !== "unavailable") {
        intro.dataset.presentationState = "unavailable";
        const scene = intro.querySelector("[data-presentation-scene]");
        const message = document.createElement("p");
        message.textContent = "3D-презентация недоступна.";
        message.setAttribute("role", "status");
        scene?.append(message);
        intro.querySelectorAll("[data-presentation-pause], [data-assembly-range]")
          .forEach((control) => { control.disabled = true; });
      }
      console.warn("Не удалось запустить 3D-презентацию.", error);
    }
  }
}

async function enterFeatureTour(version) {
  try {
    const { mountFeatureTour } = await import("./presentation-demo.js");
    if (version === revision) cleanupFeatureTour = mountFeatureTour(intro);
  } catch (error) {
    console.warn("Не удалось запустить обзор возможностей.", error);
  }
}

function enterWorkbench() {
  // One import for the lifetime of the document keeps the current project and worker.
  workbenchImport ??= import("./app.js").then(
    () => colorScheme.removeEventListener("change", applyInitialTheme),
    (error) => {
      const status = workbench.querySelector("#engine-status") || document.createElement("p");
      status.textContent = "Расчёт не загрузился. Обновите страницу, чтобы повторить попытку.";
      status.setAttribute("role", "alert");
      if (!status.isConnected) workbench.prepend(status);
      console.error("Не удалось запустить DriveLab.", error);
    },
  );
  workbench.dispatchEvent(new Event("drivelab-show-workbench"));
}

function route(event) {
  const screen = workbenchRoutes.has(location.hash) ? workbench : intro;
  // The workbench's legacy section router scrolls the window on every hash change.
  // Presentation hashes belong to this entry point, so do not forward them there.
  if (screen === intro) event?.stopImmediatePropagation();
  if (screen === currentScreen) return;
  const previous = currentScreen;
  currentScreen = screen;
  const version = ++revision;
  if (previous === workbench)
    workbench.querySelectorAll("dialog[open]").forEach((dialog) => dialog.close());

  intro.hidden = screen !== intro;
  workbench.hidden = screen !== workbench;
  if (previous) focusScreen(screen);

  if (screen === intro) {
    void enterPresentation(version);
    void enterFeatureTour(version);
  } else {
    cleanupFeatureTour?.();
    cleanupFeatureTour = undefined;
    const cleanup = cleanupPresentation;
    cleanupPresentation = undefined;
    try {
      cleanup?.();
    } catch (error) {
      console.warn("Не удалось завершить 3D-презентацию.", error);
    }
    enterWorkbench();
  }
}

applyInitialTheme();
colorScheme.addEventListener("change", applyInitialTheme);
addEventListener("hashchange", route, { capture: true });
route();
