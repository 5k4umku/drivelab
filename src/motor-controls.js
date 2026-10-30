import { fmt, escapeHTML as e } from "./format.js";
const catalog = await fetch(new URL("./motors.json", import.meta.url)).then(
  (r) => r.json(),
);
export function motorControls(root, p, onChange) {
  const selected = p.motor?.id || "none",
    custom = selected === "custom";
  const m = custom ? p.motor : catalog.find((m) => m.id === selected);
  const field = (key, label, value) =>
    `<label class="builder-field">${label}<input data-motor="${key}" type="${["name", "source"].includes(key) ? "text" : "number"}" value="${e(value)}" step="any"></label>`;
  root.innerHTML = `<div class="builder-section-title"><div><h2>Двигатель и корпус</h2><p>Прямое соединение с входным валом. Мощность на входе — механическая нагрузка.</p></div></div><div class="builder-card motor-card"><div class="builder-fields"><label class="builder-field">Двигатель<select id="motor-choice"><option value="none">Без выбора двигателя</option>${catalog.map((m) => `<option value="${m.id}" ${selected === m.id ? "selected" : ""}>${e(m.name)} · ${fmt(m.power)} кВт · ${m.speed} мин⁻¹</option>`).join("")}<option value="custom" ${custom ? "selected" : ""}>Свой двигатель</option></select></label><label class="builder-field">Корпус в модели<select id="housing-mode">${Object.entries(
    {
      contour: "Габаритный контур",
      transparent: "Прозрачный эскиз",
      hidden: "Скрыть",
    },
  )
    .map(
      ([v, l]) =>
        `<option value="${v}" ${(p.housing?.mode ?? "contour") === v ? "selected" : ""}>${l}</option>`,
    )
    .join(
      "",
    )}</select></label><label class="builder-field">Габаритный зазор корпуса, мм<input id="housing-clearance" type="number" min="5" max="200" step="1" value="${p.housing?.clearance ?? 20}"></label></div>${m ? `<p class="motor-summary"><b>${e(m.name)}</b> · ${fmt(m.power)} кВт · ${fmt(m.speed, 0)} мин⁻¹ · η=${fmt(m.efficiency)} · Kп=${fmt(m.startup)}${!custom ? ` · <a href="${e(m.source)}" target="_blank" rel="noopener">Паспорт Omec Motors ↗</a>` : ""}</p>` : ""}${custom ? `<div class="builder-fields">${field("name", "Название", m.name)}${field("power", "Мощность номинальная, кВт", m.power)}${field("speed", "Частота номинальная, мин⁻¹", m.speed)}${field("efficiency", "КПД", m.efficiency)}${field("startup", "Tпуск / Tном", m.startup)}${field("frame", "Высота оси, мм (для эскиза)", m.frame)}${field("source", "Источник паспортных данных", m.source)}</div>` : ""}<p class="field-note">Выбор двигателя переносит его номинальные P и n на вход. Затем можно задать меньшую рабочую мощность. Пусковой момент берётся от номинала двигателя. Корпус и двигатель показаны условно; присоединительные размеры требуют чертежа изготовителя.</p></div>`;
  root.querySelector("#motor-choice").onchange = (event) => {
    const q = structuredClone(p),
      id = event.target.value;
    q.motor =
      id === "none"
        ? null
        : id === "custom"
          ? {
              id: "custom",
              name: "Мой двигатель",
              power: p.power,
              speed: p.speed,
              efficiency: 0.8,
              startup: 2.3,
              frame: 90,
              source: "Паспорт двигателя — уточнить",
            }
          : { id };
    const data = id === "custom" ? q.motor : catalog.find((m) => m.id === id);
    if (data) {
      q.power = data.power;
      q.speed = data.speed;
    }
    onChange(q);
  };
  root.querySelectorAll("[data-motor]").forEach(
    (el) =>
      (el.onchange = () => {
        const q = structuredClone(p),
          k = el.dataset.motor;
        q.motor[k] = ["name", "source"].includes(k)
          ? el.value
          : Number(el.value);
        if (k === "speed") q.speed = q.motor.speed;
        onChange(q);
      }),
  );
  for (const id of ["housing-mode", "housing-clearance"])
    root.querySelector("#" + id).onchange = () => {
      const q = structuredClone(p);
      q.housing = {
        mode: root.querySelector("#housing-mode").value,
        clearance: Number(root.querySelector("#housing-clearance").value),
      };
      onChange(q);
    };
}
