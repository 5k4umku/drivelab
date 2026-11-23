import { escapeHTML as e } from "./format.js";

const publicFields = new Set(["spectrum","spectrumMethod","typicalMoments","materials","tool1","tool2","refineContact","refineBending","faceFactorsConfirmed","surfaceConfirmed","peakProbabilityFactor","peakProbabilityFactorConfirmed"]);
const numeric = (p, key, label, attrs = 'step="any"') =>
  `<label class="field">${label}<input name="${key}" type="number" ${attrs} value="${e(p[key])}" required></label>`;
const sampleMaterials = [310,280].map((hb,i) => ({
  row:"16.1", label:i ? "Улучшенная сталь колеса" : "Улучшенная сталь шестерни",
  evidence:"Учебный пример. Укажите паспорт заготовки и технологическую карту.",
  hb, hv:i ? 295 : 325, yieldStrength:i ? 685 : 785,
  blank:i ? "rolled" : "forged", grinding:"none", rootTreatment:"none"
}));
const docs = "https://github.com/5k4umku/drivelab/blob/main/docs/gost-inputs.md";
const materialValue = value => value == null ? "" : JSON.stringify(value, null, 2);

export function gostFields(p) {
  const cfg = p.gost || {};
  const other = Object.fromEntries(Object.entries(cfg).filter(([key]) => !publicFields.has(key)));
  const tool = i => `<label class="field">Инструмент ${i === 1 ? "шестерни" : "колеса"}<select name="tool${i}"><option value="standard">Стандартная рейка</option><option value="protuberance" ${cfg["tool"+i] === "protuberance" ? "selected" : ""}>С протуберанцем · табл. 13.6</option></select></label>`;
  return `<fieldset><legend>Проверка по ГОСТ 21354–87</legend>
    ${p.meshType === "internal" ? '<p class="field-note">Для внутренней пары используется геометрия по ГОСТ 19274–73. Проверка прочности по ГОСТ 21354–87 относится к внешнему зацеплению.</p>' : `
    <label class="field">Геометрия ступени<select name="geometryMode"><option value="design">Подобрать по семинару</option><option value="given" ${p.geometryMode === "given" ? "selected" : ""}>Проверить по чертежу</option></select></label>
    <div data-given><div class="field-grid">${numeric(p,"manualModule","Нормальный модуль, мм")}${numeric(p,"manualWidth","Активная ширина, мм")}${numeric(p,"manualZ1","Число зубьев шестерни","min=1 step=1")}${numeric(p,"manualZ2","Число зубьев колеса","min=1 step=1")}${numeric(p,"manualBeta","Угол наклона β, °")}${numeric(p,"x1","Смещение шестерни x₁")}${numeric(p,"x2","Смещение колеса x₂")}</div>
    <p class="field-note">Рабочий угол и межосевое расстояние определяются по смещениям. У прямозубой пары β = 0. Для шеврона укажите сумму активных ширин обеих половин.</p></div>
    <div class="field-grid">${tool(1)}${tool(2)}</div>
    <label class="checkbox-field"><input type="checkbox" name="refineContact" ${cfg.refineContact ? "checked" : ""}> Проверить зоны контакта косых зубьев по приложению 7</label>
    <label class="checkbox-field"><input type="checkbox" name="refineBending" ${cfg.refineBending ? "checked" : ""}> Уточнить изгиб прямых зубьев по приложению 9</label>
    <details ${cfg.spectrum ? "open" : ""}><summary>Циклограмма и обратный ход</summary><p class="field-note">При постоянной частоте задайте в каждой строке момент в долях номинального и процент ресурса. Отрицательный момент нагружает обратную сторону зуба. Сумма времени — 100 %. Пустое поле возвращает расчёт к выбранному режиму 0–V или ручным коэффициентам.</p>
    <label class="field">Метод приложения 3<select name="spectrumMethod">${[["moments","2 · эквивалентные моменты"],["cycles","1 · эквивалентные циклы"],["stresses","3 · эквивалентные напряжения"]].map(([key,label])=>`<option value="${key}" ${key===cfg.spectrumMethod?"selected":""}>${label}</option>`).join("")}</select></label><label class="checkbox-field"><input name="typicalMoments" type="checkbox" ${cfg.typicalMoments?"checked":""}> Для типового режима 0–V считать эквивалентные моменты по таблице 36</label><label class="field">Момент / ресурс, % / частота в долях номинальной (для методов 1 и 3)<textarea name="spectrumRows" rows="4" placeholder="1  60&#10;0,7  30&#10;−0,4  10">${e((cfg.spectrum || []).map(x=>x.torqueRatio+"  "+Number((100*x.timeFraction).toPrecision(12))+(x.speedRatio!=null?"  "+x.speedRatio:"")).join("\n"))}</textarea></label></details>
    <details ${cfg.materials ? "open" : ""}><summary>Паспорта шестерни и колеса</summary><p class="field-note">Две записи содержат строку табл. 14–17, свойства и обработку каждой заготовки. HB, HV и HRC вводятся по источнику. Паспорта применяются в проверочном расчёте.</p>
    <button type="button" class="secondary" data-material-sample>Вставить пример У / У</button><label class="field">Два паспорта в формате JSON<textarea name="materialPassports" spellcheck="false" rows="7">${e(materialValue(cfg.materials))}</textarea></label></details>
    <details ${Object.keys(other).length ? "open" : ""}><summary>Дополнительные условия и измерения</summary><label class="field">Добавить группу полей<select data-gost-template><option value="">Выберите расчёт…</option><option value="face27">Распределение по ширине · приложение 6</option><option value="dynamics">Резонанс · приложение 5</option><option value="peakLoad">Пуск машины · таблица 24</option><option value="design">Проектировочные размеры · раздел 5</option><option value="criteria">Ресурс · таблицы 1–2</option></select></label><label class="field">Параметры ГОСТ в формате JSON<textarea name="gostExtra" spellcheck="false" rows="5" placeholder='{"aAlpha": 0.7, "yAlpha": 2}'>${e(Object.keys(other).length ? materialValue(other) : "")}</textarea></label><p class="field-note"><a href="${docs}" target="_blank" rel="noreferrer">Поля, единицы и проверочные примеры</a></p></details>`}
    <a href="?example=gost-annex-11" target="_blank" rel="noopener">Открыть пример из приложения 11 в отдельной вкладке ↗</a>
    </fieldset>`;
}

export function bindGostFields(root) {
  const mode = root.querySelector('[name=geometryMode]');
  if (!mode) return;
  const refresh = () => {
    const block = root.querySelector('[data-given]');
    block.hidden = mode.value !== "given";
    for (const field of block.querySelectorAll('input')) field.disabled = block.hidden;
  };
  mode.addEventListener("change",refresh);
  refresh();
  root.querySelector('[data-gost-template]').onchange = event => {
    const el=root.querySelector('[name=gostExtra]');
    const presets={face27:{span:120,distance:60,bearing:"ball",torques:"opposite",scheme:0,hv:300},dynamics:{pitchError:10,profileError:8},peakLoad:{machine:"fan"},design:{},criteria:{lifeLimitHours:100000}};
    const key=event.target.value;
    if(!key) return;
    try {
      const current=JSON.parse(el.value.trim() || "{}");
      if (!current || Array.isArray(current) || typeof current !== "object") throw Error();
      if(!(key in current)) current[key]=presets[key];
      el.value=materialValue(current);
      el.dispatchEvent(new Event("change",{bubbles:true}));
    } catch { el.setCustomValidity("Сначала исправьте JSON дополнительных условий."); el.reportValidity(); }
    event.target.value=""; el.focus();
  };
  root.querySelector('[name=gostExtra]').oninput=event=>event.target.setCustomValidity("");
  root.querySelector('[data-material-sample]').onclick = () => {
    const field=root.querySelector('[name=materialPassports]');
    if (field.value.trim()) { field.focus(); return; }
    field.value=materialValue(sampleMaterials);
    field.dispatchEvent(new Event("change",{bubbles:true}));
  };
}

export function readGostFields(form, previous) {
  if (!form.has("geometryMode")) return previous || {};
  function parse(key, label) {
    const raw = String(form.get(key) || "").trim();
    try { return raw ? JSON.parse(raw) : undefined; }
    catch { throw Error("Проверьте JSON в поле «"+label+"»."); }
  }
  const cfg = parse("gostExtra","Дополнительные условия") ?? {};
  if (typeof cfg !== "object" || Array.isArray(cfg) || Object.keys(cfg).some(k=>publicFields.has(k)))
    throw Error("Дополнительные условия должны быть объектом без повторения настроек формы.");
  const materials = parse("materialPassports","Паспорта материалов");
  if (materials !== undefined) {
    if (!Array.isArray(materials) || materials.length !== 2) throw Error("Введите два паспорта в порядке шестерня, колесо.");
    cfg.materials = materials;
  }
  for(const k of ["tool1","tool2"]) if(form.get(k)==="protuberance") cfg[k]="protuberance";
  for(const k of ["refineContact","refineBending"]) if(form.has(k)) cfg[k]=true;
  const raw = String(form.get("spectrumRows") || "").trim();
  if(form.has("typicalMoments")) cfg.typicalMoments=true;
  if (raw) {
    if(cfg.typicalMoments) throw Error("Выберите типовую нагрузку или пользовательскую циклограмму.");
    const method=form.get("spectrumMethod");
    if(method!=="moments") cfg.spectrumMethod=method;
    cfg.spectrum = raw.split(/\r?\n/).filter(row=>row.trim()).map((row,i)=>{
      const nums=row.trim().replaceAll("−","-").replaceAll(",",".").split(/[;\s]+/).map(Number);
      if(nums.length<2 || nums.length>(method==="moments"?2:3) || (nums[2]<0 || (nums[2]===0 && nums[0]!==0)) || !nums.every(Number.isFinite) || nums[1]<=0 || nums[1]>100)
        throw Error("Циклограмма, строка "+(i+1)+". Введите момент и долю ресурса в процентах.");
      return {torqueRatio:nums[0],timeFraction:nums[1]/100,...(nums.length===3?{speedRatio:nums[2]}:{})};
    });
    if(Math.abs(cfg.spectrum.reduce((a,r)=>a+r.timeFraction,0)-1)>1e-8) throw Error("Сумма времени в циклограмме должна составлять 100 %.");
  }
  return cfg;
}
