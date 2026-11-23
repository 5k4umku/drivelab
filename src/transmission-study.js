import { fmt } from "./format.js";

const stylesheet = document.createElement("link");
stylesheet.rel = "stylesheet";
stylesheet.href = new URL("./transmission-study.css", import.meta.url);
document.head.append(stylesheet);

let activeStudy;

export function updateTransmissionStudy(assembly, activeStage) {
  const scene = document.querySelector("#assembly-view");
  const controls = scene?.nextElementSibling;
  const stage = assembly.stages[activeStage];
  const pair = stage?.result?.chosen;
  if (!scene || !controls?.classList.contains("scene-tools") || !pair) return;

  if (activeStudy?.scene !== scene || activeStudy?.controls !== controls) {
    activeStudy?.observer.disconnect();
    activeStudy?.element.remove();
    activeStudy = createStudy(scene, controls);
  }
  if (!activeStudy) return;

  const { element, update } = activeStudy;
  element.querySelector(".study-stage").textContent = `Ступень ${activeStage + 1}`;
  element.querySelector(".study-ratio").textContent = `${pair.z1} : ${pair.z2}`;
  const distance = stage.result.a ?? pair.a;
  element.querySelector(".study-dimension").textContent = Number.isFinite(distance)
    ? `a = ${fmt(distance, 2)} мм` : "";
  update();
}

function createStudy(scene, controls) {
  const view = controls.querySelector('[data-effect="iso"]');
  const contact = controls.querySelector('[data-effect="contact"]');
  const range = controls.querySelector("input[type=range]");
  if (!view || !contact || !range) return;

  const element = document.createElement("div");
  element.className = "transmission-study";
  element.innerHTML = `
    <div class="study-tool">
      <span class="study-label">Разбор передачи</span>
      <div class="study-modes" role="group" aria-label="Разбор передачи">
        <button type="button" data-study-mode="assembly">Сборка</button>
        <button type="button" data-study-mode="contact">Зацепление</button>
        <button type="button" data-study-mode="exploded">Разнесение</button>
      </div>
      <label class="study-range" hidden>
        <span>Разнести</span>
        <input type="range" min="1" max="100" value="58" aria-label="Разнесение в разборе передачи">
        <output>58 %</output>
      </label>
    </div>
    <div class="study-readout">
      <span class="study-stage"></span>
      <strong class="study-ratio"></strong>
      <span class="study-dimension"></span>
    </div>
  `;
  scene.append(element);

  const buttons = [...element.querySelectorAll("[data-study-mode]")];
  const label = element.querySelector(".study-range");
  const slider = label.querySelector("input");
  const output = label.querySelector("output");

  function setSeparation(value) {
    range.value = String(value);
    range.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function update() {
    const separation = Number(range.value);
    const mode = separation > 0 ? "exploded"
      : contact.getAttribute("aria-pressed") === "true" ? "contact" : "assembly";
    element.dataset.mode = mode;
    for (const button of buttons) {
      button.setAttribute("aria-pressed", String(button.dataset.studyMode === mode));
    }
    label.hidden = mode !== "exploded";
    if (separation > 0) {
      slider.value = String(separation);
      output.textContent = `${separation} %`;
    }
  }

  for (const button of buttons) {
    button.addEventListener("click", () => {
      if (button.dataset.studyMode === "contact") {
        contact.click();
      } else {
        view.click();
        setSeparation(button.dataset.studyMode === "exploded" ? 58 : 0);
      }
      update();
    });
  }
  slider.addEventListener("input", () => {
    setSeparation(slider.value);
    update();
  });

  const observer = new MutationObserver(update);
  observer.observe(controls, {
    subtree: true,
    attributes: true,
    attributeFilter: ["aria-pressed", "aria-valuetext"],
  });
  return { scene, controls, element, observer, update };
}
