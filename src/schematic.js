import { fmt, escapeHTML as e } from "./format.js";

/** SVG is a view of Python geometry. A gesture edits the project, then Python
 * recalculates both views. Coordinates are millimetres; drawings are schematic. */
export class SchematicEditor {
  constructor(root, getProject, onChange) {
    this.root = root;
    this.getProject = getProject;
    this.onChange = onChange;
    this.mode = "axial";
    this.selected = null;
    this.undo = [];
    this.redo = [];
    root.innerHTML = `<div class="builder-section-title"><div><div class="eyebrow">КОМПОНОВКА НА ЧЕРТЕЖЕ</div><h2>Редактор схемы</h2><p>Перетащите венец или опору. Пара зацепления перемещается совместно.</p></div></div><div class="schematic-toolbar"><button data-plane="axial" class="active">Развёртка вдоль валов</button><button data-plane="front">Вид с торца · схема ступеней</button><button id="scheme-undo" aria-label="Отменить перемещение" disabled>↶</button><button id="scheme-redo" aria-label="Повторить перемещение" disabled>↷</button><button id="scheme-save">↓ Схема SVG</button></div><div class="schematic-canvas" id="scheme-canvas"></div><div id="scheme-inspector" class="scheme-inspector" aria-live="polite">Выберите элемент на схеме.</div><p class="field-note">Развёртка разносит валы по строкам: масштаб вдоль Z общий, межосевые расстояния смотрите с торца. При ручном перемещении текущие положения остальных венцов и опор фиксируются. Стрелки клавиатуры — 1 мм / 1°, Shift — 10. Корпус и подшипники обозначены условно.</p>`;
    root.querySelectorAll("[data-plane]").forEach(
      (el) =>
        (el.onclick = () => {
          this.mode = el.dataset.plane;
          this.draw();
        }),
    );
    root.querySelector("#scheme-undo").onclick = () => this.restore(false);
    root.querySelector("#scheme-redo").onclick = () => this.restore(true);
    root.querySelector("#scheme-save").onclick = () => {
      const svg = root.querySelector("svg");
      if (!svg) return;
      const blob = new Blob([new XMLSerializer().serializeToString(svg)], {
          type: "image/svg+xml;charset=utf-8",
        }),
        a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "DriveLab-scheme.svg";
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    };
  }
  update(data) {
    if (
      this.data &&
      !this.localChange &&
      JSON.stringify(data.project) !== JSON.stringify(this.data.project)
    ) {
      this.undo = [];
      this.redo = [];
      this.selected = null;
    }
    this.localChange = false;
    this.data = data;
    this.draw();
  }
  commit(p) {
    this.undo.push(structuredClone(this.getProject()));
    if (this.undo.length > 40) this.undo.shift();
    this.redo = [];
    this.localChange = true;
    this.onChange(p);
  }
  restore(forward) {
    const from = forward ? this.redo : this.undo,
      to = forward ? this.undo : this.redo;
    if (!from.length) return;
    to.push(structuredClone(this.getProject()));
    this.localChange = true;
    this.onChange(from.pop());
  }
  fixedProject() {
    const p = structuredClone(this.getProject());
    this.data.stages.forEach((s, i) => (p.stages[i].axial = s.axial));
    this.data.shafts.forEach((s, i) =>
      Object.assign(p.shafts[i], { layout: "manual", zA: s.A.z, zB: s.B.z }),
    );
    return p;
  }
  value(target) {
    return target.kind === "gear"
      ? this.data.stages[target.index].axial
      : target.kind === "bearing"
        ? this.data.shafts[target.index][target.side].z
        : this.data.stages[target.index].angle;
  }
  move(target, value) {
    if (!Number.isFinite(value)) return;
    const p = this.fixedProject();
    if (target.kind === "gear")
      p.stages[target.index].axial = Math.max(-100000, Math.min(100000, value));
    if (target.kind === "bearing") {
      const s = p.shafts[target.index];
      s["z" + target.side] =
        target.side === "A"
          ? Math.min(value, s.zB - 1)
          : Math.max(value, s.zA + 1);
    }
    if (target.kind === "axis") p.stages[target.index].angle = value;
    this.selected = target;
    this.commit(p);
  }
  inspector() {
    const t = this.selected,
      root = this.root.querySelector("#scheme-inspector");
    if (!t) {
      root.textContent =
        this.mode === "axial"
          ? "Венцы — зелёные блоки, опоры — синие и золотые."
          : "Перемещайте центр выходного вала ступени по окружности: межосевое расстояние сохраняется.";
      return;
    }
    if (
      (t.kind === "bearing" ? this.data.shafts : this.data.stages)[t.index] ===
      undefined
    ) {
      this.selected = null;
      this.inspector();
      return;
    }
    const label =
      t.kind === "gear"
        ? `Зацепление ${t.index + 1} · положение обоих венцов`
        : t.kind === "bearing"
          ? `Вал ${t.index + 1} · опора ${t.side}`
          : `Ступень ${t.index + 1} · направление в XY`;
    root.innerHTML = `<label>${label}<input id="scheme-coordinate" type="number" step="1" value="${this.value(t)}">${t.kind === "axis" ? "°" : "мм"}</label><button id="scheme-apply">Применить</button><span>Изменение пересчитает 3D, реакции опор и выбор Т5.</span>`;
    const apply = () => this.move(t, Number(root.querySelector("input").value));
    root.querySelector("button").onclick = apply;
    root.querySelector("input").onkeydown = (event) => {
      if (event.key === "Enter") apply();
    };
  }
  draw() {
    if (!this.data?.shafts.length) return;
    this.root
      .querySelectorAll("[data-plane]")
      .forEach((el) =>
        el.classList.toggle("active", el.dataset.plane === this.mode),
      );
    this.root.querySelector("#scheme-undo").disabled = !this.undo.length;
    this.root.querySelector("#scheme-redo").disabled = !this.redo.length;
    const body = this.mode === "axial" ? this.axial() : this.front();
    this.root.querySelector("#scheme-canvas").innerHTML = body;
    this.inspector();
    this.bind();
  }
  svg(content, width, height) {
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" role="group" aria-label="Редактируемая кинематическая схема редуктора"><style>text{font-family:Arial,sans-serif;fill:#263e4c;font-size:11px}.axis{stroke:#78939e;stroke-width:1;stroke-dasharray:7 4}.shaft{stroke:#455e6f;stroke-width:5}.venet{fill:#d1eee1;stroke:#147b5c;stroke-width:1.5}.support{fill:#e0ebf1;stroke:#4c718a;stroke-width:1.5}.fixed{fill:#f7e3bf;stroke:#ab7835}.house{fill:#eaf1ee;fill-opacity:.35;stroke:#9ebbb0;stroke-width:1.5;stroke-dasharray:5 4}[data-drag]{cursor:grab;outline:none}[data-drag]:focus>*{stroke:#dd6f32;stroke-width:2.5}[data-drag]:hover .venet,[data-drag]:hover .support{fill:#b4e0ce}.dimension{fill:#68808a;font-size:10px}.connector{stroke:#3f8e78;stroke-dasharray:3 3;stroke-width:1;fill:none}</style><rect width="100%" height="100%" fill="#fbfdfc"/><text x="20" y="25" style="font-weight:bold;font-size:14px">${e(this.data.project.name)}</text>${content}</svg>`;
  }
  axial() {
    const d = this.data,
      W = 1000,
      H = Math.max(300, 125 + d.shafts.length * 100),
      motor = d.motor,
      clearance = d.project.housing?.clearance ?? 20;
    const lo =
        Math.min(...d.shafts.map((s) => s.zMin)) -
        (motor ? motor.frame * 2.5 : clearance + 25),
      hi = Math.max(...d.shafts.map((s) => s.zMax)) + clearance + 25;
    const scale = 780 / (hi - lo),
      X = (z) => 160 + (z - lo) * scale,
      Y = (i) => 100 + i * 100;
    this.transform = { scale, X, Y, lo };
    const minZ = Math.min(
        ...d.shafts.map((s) => s.A.z),
        ...d.gears.map((g) => g.z - g.width / 2),
      ),
      maxZ = Math.max(
        ...d.shafts.map((s) => s.B.z),
        ...d.gears.map((g) => g.z + g.width / 2),
      );
    let content =
      d.project.housing?.mode === "hidden"
        ? ""
        : `<rect class="house" x="${X(minZ - clearance)}" y="58" width="${(maxZ - minZ + 2 * clearance) * scale}" height="${H - 95}" rx="10"/><text x="${X(minZ) - 10}" y="74" class="dimension">Корпус · габаритный эскиз</text>`;
    for (const s of d.shafts) {
      const y = Y(s.index);
      content += `<text x="20" y="${y - 7}" style="font-weight:bold">Вал ${s.index + 1}</text><text x="20" y="${y + 10}" class="dimension">${fmt(s.speed, 1)} мин⁻¹</text><line class="axis" x1="${X(lo)}" y1="${y}" x2="960" y2="${y}"/><line class="shaft" x1="${X(s.zMin)}" y1="${y}" x2="${X(s.zMax)}" y2="${y}"/>`;
      for (const name of ["A", "B"]) {
        const x = X(s[name].z),
          fixed = name === s.locating;
        const inside =
          s.bearing === "ball"
            ? `<circle cx="${x}" cy="${y - 11}" r="4"/><circle cx="${x}" cy="${y + 11}" r="4"/>`
            : `<rect x="${x - 5}" y="${y - 15}" width="10" height="7"/><rect x="${x - 5}" y="${y + 8}" width="10" height="7"/>`;
        content += `<g data-drag="bearing" data-index="${s.index}" data-side="${name}" tabindex="0" role="button" aria-label="Переместить опору ${name} вала ${s.index + 1}"><rect class="support ${fixed ? "fixed" : ""}" x="${x - 10}" y="${y - 21}" width="20" height="42" rx="2"/><g fill="none" stroke="#5c7788">${inside}</g><text x="${x}" y="${y + 39}" text-anchor="middle">${name} ${fmt(s[name].z, 1)}</text></g>`;
      }
    }
    for (const s of d.stages) {
      const x = X(s.axial),
        a = Y(s.index),
        b = Y(s.index + 1);
      content += `<path class="connector" data-pair="${s.index}" d="M${x} ${a + 28} V${b - 28}"/><text x="${x + 6}" y="${(a + b) / 2}" class="dimension">${s.index + 1} · ${s.result.input.meshType === "internal" ? "внутр." : "внеш."}</text>`;
    }
    for (const g of d.gears) {
      const x = X(g.z),
        y = Y(g.shaft),
        w = Math.max(12, g.width * scale),
        kind = d.stages[g.stage].result.input.gearType;
      const tooth =
        kind === "spur"
          ? `M${x - 3} ${y - 24} V${y + 24} M${x + 3} ${y - 24} V${y + 24}`
          : kind === "helical"
            ? `M${x - w * 0.3} ${y + 23} L${x + w * 0.3} ${y - 23}`
            : `M${x - w * 0.35} ${y - 23} L${x + w * 0.35} ${y} L${x - w * 0.35} ${y + 23}`;
      content += `<g data-drag="gear" data-index="${g.stage}" data-pair="${g.stage}" tabindex="0" role="button" aria-label="Переместить зацепление ${g.stage + 1} по валам"><rect class="venet" x="${x - w / 2}" y="${y - 26}" width="${w}" height="52" rx="2"/><path d="${tooth}" fill="none" stroke="#267f64"/><text x="${x}" y="${y - 33}" text-anchor="middle">z${g.side}=${d.stages[g.stage].result.chosen["z" + g.side]}</text></g>`;
    }
    if (motor) {
      const x = X(d.shafts[0].zMin) - 50,
        y = Y(0);
      content += `<line class="shaft" x1="${x}" y1="${y}" x2="${X(d.shafts[0].zMin)}" y2="${y}"/><circle cx="${x - 28}" cy="${y}" r="28" fill="#e8edf3" stroke="#415d78" stroke-width="2"/><text x="${x - 28}" y="${y + 6}" text-anchor="middle" style="font-size:20px">М</text><text x="${x - 28}" y="${y + 45}" text-anchor="middle">${e(motor.name)}</text>`;
    }
    content += `<line x1="${X(lo)}" y1="${H - 25}" x2="940" y2="${H - 25}" stroke="#9fb2bc"/><text x="160" y="${H - 8}" class="dimension">Z=${fmt(lo, 1)} мм</text><text x="940" y="${H - 8}" text-anchor="end" class="dimension">${fmt(hi, 1)} мм → Z</text>`;
    return this.svg(content, W, H);
  }
  front() {
    const d = this.data,
      b = d.bounds,
      W = 1000,
      H = 600,
      clearance = d.project.housing?.clearance ?? 20,
      spanX = b[1] - b[0],
      spanY = b[3] - b[2],
      scale = Math.min(
        860 / (spanX + 2 * clearance + 40),
        460 / (spanY + 2 * clearance + 40),
      );
    const X = (x) => 500 + (x - (b[0] + b[1]) / 2) * scale,
      Y = (y) => 320 - (y - (b[2] + b[3]) / 2) * scale;
    this.transform = { scale, X, Y };
    let content =
      d.project.housing?.mode === "hidden"
        ? ""
        : `<rect class="house" x="${X(b[0] - clearance)}" y="${Y(b[3] + clearance)}" width="${(spanX + 2 * clearance) * scale}" height="${(spanY + 2 * clearance) * scale}" rx="12"/>`;
    for (const g of [...d.gears].sort((a, b) => b.radius - a.radius)) {
      content += `<circle cx="${X(g.x)}" cy="${Y(g.y)}" r="${g.radius * scale}" fill="#d1eee1" fill-opacity=".22" stroke="#629f8b"/><circle cx="${X(g.x)}" cy="${Y(g.y)}" r="${g.pitchRadius * scale}" fill="none" stroke="#5899ac" stroke-dasharray="4 3"/>`;
    }
    for (const g of d.gears.filter((g) => g.innerRadius))
      content += `<circle cx="${X(g.x)}" cy="${Y(g.y)}" r="${g.innerRadius * scale}" fill="none" stroke="#147b5c" stroke-width="2"/>`;
    for (const s of d.stages) {
      const a = d.shafts[s.index],
        b = d.shafts[s.index + 1];
      content += `<line class="connector" x1="${X(a.x)}" y1="${Y(a.y)}" x2="${X(b.x)}" y2="${Y(b.y)}"/><text x="${(X(a.x) + X(b.x)) / 2}" y="${(Y(a.y) + Y(b.y)) / 2 - 8}" text-anchor="middle">aw=${fmt(s.result.chosen.a, 1)} мм</text>`;
    }
    for (const s of d.shafts) {
      content += `<g ${s.index ? `data-drag="axis" data-index="${s.index - 1}" tabindex="0" role="button" aria-label="Изменить направление ступени ${s.index}"` : ""}><circle cx="${X(s.x)}" cy="${Y(s.y)}" r="15" fill="${s.index ? "#1a7a60" : "#284858"}" stroke="#fff" stroke-width="2"/><text x="${X(s.x)}" y="${Y(s.y) + 4}" text-anchor="middle" style="fill:white;font-weight:bold">${s.index + 1}</text></g>`;
    }
    content +=
      '<text x="20" y="580" class="dimension">Пунктир — делительные окружности. Номера обозначают валы. Осевое положение показано на развёртке.</text>';
    return this.svg(content, W, H);
  }
  bind() {
    const svg = this.root.querySelector("svg");
    let drag;
    const point = (event) => {
      const p = svg.createSVGPoint();
      p.x = event.clientX;
      p.y = event.clientY;
      return p.matrixTransform(svg.getScreenCTM().inverse());
    };
    svg.onpointerdown = (event) => {
      const el = event.target.closest("[data-drag]");
      if (!el) return;
      const target = {
        kind: el.dataset.drag,
        index: Number(el.dataset.index),
        side: el.dataset.side,
      };
      this.selected = target;
      this.inspector();
      drag = {
        target,
        start: point(event),
        initial: this.value(target),
        value: this.value(target),
        id: event.pointerId,
      };
      svg.setPointerCapture(event.pointerId);
      el.focus();
      event.preventDefault();
    };
    svg.onpointermove = (event) => {
      if (!drag) return;
      const p = point(event),
        dx = p.x - drag.start.x,
        t = drag.target;
      if (t.kind === "axis") {
        const s = this.data.shafts[t.index];
        drag.value =
          (Math.atan2(
            this.transform.Y(s.y) - p.y,
            p.x - this.transform.X(s.x),
          ) *
            180) /
          Math.PI;
      } else {
        drag.value =
          Math.round((drag.initial + dx / this.transform.scale) * 10) / 10;
        const selector =
          t.kind === "gear"
            ? `[data-pair="${t.index}"]`
            : `[data-drag="bearing"][data-index="${t.index}"][data-side="${t.side}"]`;
        svg
          .querySelectorAll(selector)
          .forEach((el) => el.setAttribute("transform", `translate(${dx} 0)`));
      }
      this.root.querySelector("#scheme-coordinate").value = drag.value;
    };
    svg.onpointerup = (event) => {
      if (!drag) return;
      const d = drag;
      drag = null;
      svg.releasePointerCapture(event.pointerId);
      if (Math.abs(d.value - d.initial) > 0.01) this.move(d.target, d.value);
    };
    svg.onpointercancel = () => {
      drag = null;
      this.draw();
    };
    svg.querySelectorAll("[data-drag]").forEach(
      (el) =>
        (el.onkeydown = (event) => {
          if (
            !["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(
              event.key,
            )
          )
            return;
          event.preventDefault();
          const t = {
            kind: el.dataset.drag,
            index: Number(el.dataset.index),
            side: el.dataset.side,
          };
          this.move(
            t,
            this.value(t) +
              (["ArrowLeft", "ArrowDown"].includes(event.key) ? -1 : 1) *
                (event.shiftKey ? 10 : 1),
          );
        }),
    );
  }
}
