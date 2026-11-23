import * as THREE from "three";
import { createDrive } from "./presentation-drive.js";
import { gearMesh, meshPhase } from "./gear-geometry.js";
import { steelMaterial } from "./viewer.js";

// Snapshot from calculate_assembly at 0.75 kW and 1410 rpm. The example has two
// external helical stages, u = 3.96, and no calculated envelope collisions.
const stages = [
  {
    angle: 0, axial: 0, width: 36, hand: 1,
    geometry: {
      m: 3, z1: 20, z2: 44, beta: 17, alphaT: 20.836858467,
      d1: 62.741505389, db1: 58.638025354, da1: 68.741505389, df1: 55.241505389,
      d2: 138.031311856, db2: 129.003655778, da2: 144.031311856, df2: 130.531311856,
    },
  },
  {
    angle: 38, axial: 59, width: 30, hand: -1,
    geometry: {
      m: 3, z1: 20, z2: 36, beta: 20, alphaT: 21.172832185,
      d1: 63.850666349, db1: 59.540437788, da1: 69.850666349, df1: 56.350666349,
      d2: 114.931199427, db2: 107.172788019, da2: 120.931199427, df2: 107.431199427,
    },
  },
];
const shafts = [
  { x: 0, y: 0, min: -58.1, max: 58.1, a: -32, b: 32, rpm: 1410 },
  { x: 100.386408623, y: 0, min: -58.1, max: 114.1, a: -32, b: 88, rpm: -640.909090909 },
  { x: 170.827425013, y: 55.034553623, min: 3.9, max: 114.1, a: 30, b: 88, rpm: 356.060606061 },
];
const chapters = ["drive", "disconnect", "open", "assembly", "mesh", "power", "exploded"];
const chapterLabels = ["Привод", "Муфты", "Корпус", "Сборка", "Зацепление", "Мощность", "Разнесение"];
const cameraPeriod = 16;
const clamp = THREE.MathUtils.clamp;
const lerp = THREE.MathUtils.lerp;
const smooth = t => t*t*(3-2*t);
const firstPole = new THREE.Vector3(stages[0].geometry.d1 / 2, 0, stages[0].axial);
// Global force components on the first pinion from calculate_assembly, in N.
const firstForces = [
  { value: -61.629711653, color: 0xffad75, name: "Fr" },
  { value: -161.927489707, color: 0x81deff, name: "Ft" },
  { value: 49.506201775, color: 0xd6bcff, name: "Fa" },
];
const casing = { min: [-45, -82, -69], max: [242, 126, 125] };
const posterURL = new URL("./presentation-poster.webp", import.meta.url);

function reflectionMap(renderer) {
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 128;
  const paint = canvas.getContext("2d");
  paint.fillStyle = "#141926";
  paint.fillRect(0, 0, 256, 128);
  for (const [x, y, w, h, color] of [
    [10, 30, 54, 28, "#f1f4fb"],
    [120, 17, 20, 58, "#739bdc"],
    [188, 68, 47, 13, "#b2c9ed"],
    [66, 88, 26, 9, "#788da8"],
  ]) {
    paint.fillStyle = color;
    paint.fillRect(x, y, w, h);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.mapping = THREE.EquirectangularReflectionMapping;
  const generator = new THREE.PMREMGenerator(renderer);
  try {
    return generator.fromEquirectangular(texture);
  } finally {
    generator.dispose();
    texture.dispose();
  }
}

function createModel(scene) {
  const model = new THREE.Group();
  scene.add(model);
  const moving = [];
  const envelopes = [];
  const rotors = shafts.map(({ x, y, min, max, a, b }) => {
    const rotor = new THREE.Group();
    rotor.position.set(x, y, 0);
    model.add(rotor);
    const shaft = new THREE.Mesh(new THREE.CylinderGeometry(9, 9, max - min, 40), steelMaterial(0x818895));
    shaft.rotation.x = Math.PI / 2;
    shaft.position.z = (max + min) / 2;
    rotor.add(shaft);
    envelopes.push({ x, y, min, max, radius: 9, travel: 0 });
    for (const [position, sign] of [[a, -1], [b, 1]]) {
      const bearing = new THREE.Mesh(
        new THREE.TorusGeometry(13, 3.6, 14, 48),
        steelMaterial(sign < 0 ? 0xbcc6d5 : 0x68717f),
      );
      bearing.position.set(x, y, position);
      model.add(bearing);
      moving.push({ object: bearing, z: position, travel: 30 * sign });
      envelopes.push({ x, y, min: position - 3.6, max: position + 3.6, radius: 16.6, travel: 30 * sign });
    }
    return rotor;
  });

  for (const [index, stage] of stages.entries()) {
    for (const side of [1, 2]) {
      const gear = gearMesh(stage.geometry, side, stage.width, "helical", stage.hand,
        steelMaterial(index === 0 ? 0xb9c9dd : 0x96aac3));
      gear.position.z = stage.axial;
      gear.rotation.z = meshPhase(stage.geometry, side, THREE.MathUtils.degToRad(stage.angle), shafts[index].rpm);
      rotors[index + side - 1].add(gear);
      const travel = stage.width * (side === 1 ? -1.25 : 1.25);
      moving.push({ object: gear, z: stage.axial, travel });
      const { x, y } = shafts[index + side - 1];
      envelopes.push({ x, y, min: stage.axial - stage.width / 2, max: stage.axial + stage.width / 2,
        radius: stage.geometry[`da${side}`] / 2, travel });
    }
  }
  return { moving, rotors, envelopes };
}

function makeArrow(origin, direction, length, color, thickness = 0.48) {
  const head = Math.min(length * 0.32, 5);
  const arrow = new THREE.ArrowHelper(direction, origin, length, color, head, head * 0.66);
  arrow.line.visible = false;
  arrow.cone.material.depthTest = false;
  arrow.cone.material.toneMapped = false;
  arrow.cone.renderOrder = 6;
  const stemLength = length - head;
  const material = new THREE.MeshBasicMaterial({ color, depthTest: false, toneMapped: false });
  const stem = new THREE.Mesh(new THREE.CylinderGeometry(thickness, thickness, stemLength, 8), material);
  stem.position.y = stemLength / 2;
  stem.renderOrder = 6;
  arrow.add(stem);
  return arrow;
}

function makeExplanations(scene) {
  const forces = new THREE.Group(), power = new THREE.Group();
  scene.add(forces, power);
  forces.visible = power.visible = false;
  const maximum = Math.max(...firstForces.map(({ value }) => Math.abs(value)));
  for (const [axis, { value, color }] of firstForces.entries()) {
    const direction = new THREE.Vector3().setComponent(axis, Math.sign(value));
    forces.add(makeArrow(firstPole, direction, Math.abs(value) * 36 / maximum, color));
  }

  const [x0, y0, z0] = casing.min, [x1, y1, z1] = casing.max;
  const x = (x0 + x1) / 2, y = (y0 + y1) / 2, z = (z0 + z1) / 2;
  const width = x1 - x0, height = y1 - y0, depth = z1 - z0;
  // Three diagrammatic planes only. The front and top remain open.
  for (const [w, h, px, py, pz, rx, ry] of [
    [width, height, x, y, z0, 0, 0],
    [width, depth, x, y0, z, Math.PI / 2, 0],
    [depth, height, x1, y, z, 0, Math.PI / 2],
  ]) {
    const geometry = new THREE.PlaneGeometry(w, h);
    const panel = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({
      color: 0x8295ad, opacity: 0.11, transparent: true, side: THREE.DoubleSide,
      depthWrite: false, toneMapped: false,
    }));
    panel.position.set(px, py, pz);
    panel.rotation.set(rx, ry, 0);
    panel.add(new THREE.LineSegments(new THREE.EdgesGeometry(geometry),
      new THREE.LineBasicMaterial({ color: 0x9aaabd, transparent: true, opacity: 0.56 })));
    power.add(panel);
  }

  // The two cross-shaft portions pass through the calculated pitch points.
  const path = [
    [shafts[0].x, shafts[0].y, shafts[0].min],
    [shafts[0].x, shafts[0].y, stages[0].axial],
    [shafts[1].x, shafts[1].y, stages[0].axial],
    [shafts[1].x, shafts[1].y, stages[1].axial],
    [shafts[2].x, shafts[2].y, stages[1].axial],
    [shafts[2].x, shafts[2].y, shafts[2].max],
  ].map((point) => new THREE.Vector3(...point));
  for (let i = 1; i < path.length; i++) {
    const delta = new THREE.Vector3().subVectors(path[i], path[i - 1]);
    const length = delta.length();
    power.add(makeArrow(path[i - 1], delta.normalize(), length - 1, 0xffb177, 0.76));
  }
  return { forces, power };
}

function fitDistance(points, target, direction, up, aspect, fov) {
  const right = new THREE.Vector3().crossVectors(up, direction).normalize();
  const vertical = new THREE.Vector3().crossVectors(direction, right);
  const tangent = Math.tan(THREE.MathUtils.degToRad(fov / 2));
  const delta = new THREE.Vector3();
  let distance = 0;
  for (const point of points) {
    delta.copy(point).sub(target);
    const depth = delta.dot(direction);
    distance = Math.max(distance,
      depth + Math.abs(delta.dot(right)) / (tangent * aspect),
      depth + Math.abs(delta.dot(vertical)) / tangent);
  }
  return distance * 1.035;
}

export function mountPresentation(root) {
  const host = root?.querySelector("[data-presentation-scene]");
  if (!host) return () => {};
  const marker = [...root.querySelectorAll("[data-presentation-chapter]")];
  const interactiveChapter = "button, a, [role=button]";
  const chapterControls = document.createElement("div");
  if (!marker.some((element) => element.matches(interactiveChapter))) {
    chapterControls.setAttribute("role", "group");
    chapterControls.setAttribute("aria-label", "Виды демонстрационной модели");
    Object.assign(chapterControls.style, {
      position: "absolute", top: "12px", left: "12px", right: "12px", zIndex: "1",
      display: "flex", flexWrap: "wrap", gap: "5px", pointerEvents: "none",
    });
    for (const [index, label] of chapterLabels.entries()) {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.presentationChapter = chapters[index];
      button.textContent = label;
      Object.assign(button.style, {
        pointerEvents: "auto", minHeight: "44px", padding: "0 10px", border: "1px solid #83909d",
        borderRadius: "3px", font: "600 12px system-ui, sans-serif",
      });
      chapterControls.append(button);
      marker.push(button);
    }
    host.append(chapterControls);
  }
  const speed = root.querySelector("[data-presentation-speed]");
  const speedValue = root.querySelector("[data-presentation-speed-value]");
  const cut = root.querySelector("[data-presentation-cut]");
  const cutValue = root.querySelector("[data-presentation-cut-value]");
  const range = root.querySelector("[data-assembly-range]");
  const value = root.querySelector("[data-assembly-value]");
  const motion = matchMedia("(prefers-reduced-motion: reduce)");
  const events = new AbortController();
  const listen = (target, name, handler) =>
    target?.addEventListener(name, handler, { signal: events.signal });
  const fallback = document.createElement("img");
  fallback.alt = "Демонстрационный привод роликового конвейера с горячей заготовкой. Муфты соединяют двигатель, рассчитанный двухступенчатый редуктор и ведущий ролик.";
  fallback.src = posterURL.href;
  fallback.decoding = "async";
  Object.assign(fallback.style, { width: "100%", height: "100%", objectFit: "contain", display: "block" });
  host.append(fallback);
  const detail = document.createElement("div");
  detail.className = "presentation-scene-detail";
  detail.hidden = true;
  Object.assign(detail.style, {
    position: "absolute", left: "12px", right: "12px", bottom: "66px", zIndex: "1",
    width: "fit-content", maxWidth: "calc(100% - 24px)", padding: "7px 9px",
    color: "#edf2f8", background: "#10151eeb", borderLeft: "2px solid #ffb177",
    font: "600 12px/1.45 system-ui, sans-serif", pointerEvents: "none",
  });
  host.append(detail);

  let renderer, environment, scene, moving, rotors, envelopes, camera, forces, power, drive;
  let frame = 0, lastFrame = null, visible = false, lost = false;
  let cameraTime = 0, shaftTime = 0, displaySpeed = 1;
  let requested = 0, position = 0, chapter = "drive", explodedAmount = .76;
  let poses = [];
  const target = new THREE.Vector3(), eye = new THREE.Vector3(), up = new THREE.Vector3();
  const angles = [0,0,0];
  const multiplier = () => clamp(Number(speed?.value ?? 1), .25, 1.5);
  const rangeMin = Number(range?.min || 0), rangeMax = Number(range?.max || 100);

  function fractionalControl(input, output, fraction, min = 0, max = 100) {
    const percent = Math.round(fraction*100);
    if (input) {
      const setting = String(min + percent*(max-min)/100);
      if (input.value !== setting) input.value = setting;
      input.setAttribute("aria-valuetext", percent+" %");
    }
    if (output) output.textContent = percent+" %";
  }

  function syncControls() {
    root.dataset.presentationState = chapter;
    const label = multiplier().toLocaleString("ru-RU", {maximumFractionDigits:2})+"×";
    if (speedValue) speedValue.textContent = label;
    speed?.setAttribute("aria-valuetext", label);
    for (const element of marker) {
      const active = element.dataset.presentationChapter === chapter;
      element.toggleAttribute("data-presentation-active", active);
      if (element.matches("button, [role=button]")) element.setAttribute("aria-pressed", String(active));
      if (element.parentNode === chapterControls) {
        element.style.background = active ? "#ffb277" : "#161c23";
        element.style.color = active ? "#24180f" : "#f1f4f7";
      }
    }
    const selected = states(requested);
    fractionalControl(range, value, selected.explosion, rangeMin, rangeMax);
    fractionalControl(cut, cutValue, selected.cut);
    detail.hidden = lost || !["drive","disconnect","open","mesh","power"].includes(chapter);
    detail.replaceChildren();
    if (["drive","disconnect","open"].includes(chapter)) {
      detail.textContent = "Кожух и конвейер — демонстрационные.";
    } else if (chapter === "mesh") {
      for (const { name, value, color } of firstForces) {
        if (detail.childNodes.length) detail.append(" · ");
        const force = document.createElement("span");
        force.style.color = `#${color.toString(16).padStart(6, "0")}`;
        force.textContent = `${name} ${Math.abs(value).toLocaleString("ru-RU", { maximumFractionDigits: 1 })} Н`;
        detail.append(force);
      }
      detail.append(document.createElement("br"), "Номинальный профиль. Переход у корня условный, боковой зазор не задан.");
    } else if (chapter === "power") {
      detail.textContent = "Условный кожух · 0,750 → 0,735 → 0,720 кВт";
    }

  }

  // Section centres are keyframes. Between them the user directly scrubs each
  // mechanical action; scroll position is never changed by the renderer.
  function states(p) {
    return {
      detach: smooth(clamp(p,0,1)),
      cut: clamp(p-1,0,1),
      equipment: 1-smooth(clamp(p-2,0,1)),
      explosion: explodedAmount*smooth(clamp(p-5,0,1)),
    };
  }

  function pose(index) {
    const narrow = camera.aspect < .9;
    const directions = [[-.99,.62,.99],[-1.09,.73,.93],[-1.14,.85,.89],
      [.42,-.64,1.2],[-.36,-.43,1],[.35,.76,1.28],[.54,-.79,1.06]];
    const dir = new THREE.Vector3(...directions[index]).normalize();
    const vertical = new THREE.Vector3(index < 3 ? (narrow ? -.18 : -.08) : (narrow ? -.34 : -.18),1,0).normalize();
    const points = [];
    const corners = (min,max,offset = new THREE.Vector3()) => {
      for(const x of [min.x,max.x]) for(const y of [min.y,max.y]) for(const z of [min.z,max.z])
        points.push(new THREE.Vector3(x,y,z).add(offset));
    };
    if(index < 3) {
      drive.frameBoxes.forEach(({min,max},i)=>{
        const shift=i<2 ? Number(index>=1) : Number(index>=2);
        corners(min,max,drive.outward[i].clone().multiplyScalar(shift));
      });
    } else if(index===4){
      corners(firstPole.clone().add(new THREE.Vector3(-43.5,-34.5,-30)),
        firstPole.clone().add(new THREE.Vector3(43.5,34.5,30)));
    } else if(index===5){
      corners(new THREE.Vector3(...casing.min), new THREE.Vector3(...casing.max));
    } else {
      for (const {x,y,min,max,radius,travel} of envelopes) {
        const outside = radius / Math.cos(Math.PI/24);
        for(let i=0;i<24;i++){
          const a=i*Math.PI/12;
          const delta=index===6 ? travel*explodedAmount : 0;
          points.push(new THREE.Vector3(x+outside*Math.cos(a),y+outside*Math.sin(a),min+delta));
          points.push(new THREE.Vector3(x+outside*Math.cos(a),y+outside*Math.sin(a),max+delta));
        }
      }
    }
    const center=new THREE.Box3().setFromPoints(points).getCenter(new THREE.Vector3());
    const distance=fitDistance(points,center,dir,vertical,camera.aspect,camera.fov);
    return {center, eye:center.clone().addScaledVector(dir,distance), up:vertical};
  }

  function stopFrame() {
    cancelAnimationFrame(frame);
    frame=0;
    lastFrame=null;
  }

  function draw(now) {
    frame=0;
    if(!visible || document.hidden || lost || !renderer) return;
    const dt=lastFrame===null || motion.matches ? 0 : Math.min((now-lastFrame)/1000,.16);
    lastFrame=now;
    position=motion.matches ? requested : lerp(position,requested,1-Math.exp(-dt*8));
    if(Math.abs(requested-position)<.0001)position=requested;
    if(!motion.matches)cameraTime=(cameraTime+dt)%cameraPeriod;
    const phase=cameraTime*2*Math.PI/cameraPeriod;
    const loopWeight=1-smooth(clamp(position,0,1));
    const close=(motion.matches ? 0 : (1-Math.cos(phase))*.5)*loopWeight;
    const index=Math.floor(position), next=Math.min(index+1,6), t=smooth(position-index);
    target.lerpVectors(poses[index].center,poses[next].center,t);
    eye.lerpVectors(poses[index].eye,poses[next].eye,t);
    up.lerpVectors(poses[index].up,poses[next].up,t).normalize();
    // Periodic orbit and dolly, with equal position and tangent at both ends.
    eye.lerp(target,.32*close);
    eye.x+=Math.sin(phase)*loopWeight*21;
    target.x+=close*13;
    target.y+=close*16;
    camera.position.copy(eye);camera.up.copy(up);camera.lookAt(target);

    const near=Math.max(THREE.MathUtils.smoothstep(close,.02,.78),smooth(clamp(position-2,0,1)));
    const desired=multiplier()*lerp(1,.12,near);
    if(motion.matches)displaySpeed=desired;
    const prior=displaySpeed;
    displaySpeed=lerp(prior,desired,1-Math.exp(-dt*7));
    const advance=dt*(prior+displaySpeed)/2;
    shaftTime+=advance;
    for(const [i,rotor] of rotors.entries()){
      angles[i]=shaftTime*shafts[i].rpm*.008*Math.PI/30;
      rotor.rotation.z=angles[i];
    }
    const state=states(position);
    for(const part of moving)part.object.position.z=part.z+part.travel*state.explosion;
    drive.update(state.detach,state.cut,state.equipment,angles);
    forces.visible=Math.round(position)===4;
    power.visible=Math.round(position)===5;
    renderer.render(scene,camera);
    if(!fallback.hidden){
      fallback.hidden=true;fallback.style.display="none";renderer.domElement.hidden=false;
    }
    if(!motion.matches)schedule();
  }

  function schedule() {
    if (!frame && visible && !document.hidden && !lost && renderer) frame = requestAnimationFrame(draw);
  }

  function disposeRenderer() {
    stopFrame();
    scene?.traverse((object) => {
      if (object.isInstancedMesh) object.dispose();
      object.geometry?.dispose();
      object.material?.dispose();
    });
    drive?.dispose();
    environment?.dispose();
    if (renderer) {
      renderer.domElement.remove();
      renderer.dispose();
      renderer.forceContextLoss();
      renderer = undefined;
    }
  }

  function showPoster() {
    lost = true;
    requested=position=0;
    chapter="drive";
    syncControls();
    host.dataset.presentationFallback = "";
    fallback.hidden = false;
    fallback.style.display = "block";
    disposeRenderer();
    chapterControls.style.display = "none";
    for(const control of [range,speed,cut]) if(control)control.disabled=true;
    for(const el of marker)if(el.matches("button"))el.disabled=true;
  }

  function resize() {
    const width = host.clientWidth, height = host.clientHeight;
    if (!width || !height || lost) return;
    if (!renderer) {
      if (!visible) return;
      try {
        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setClearColor(0, 0);
        renderer.localClippingEnabled = true;
        renderer.setPixelRatio(Math.min(devicePixelRatio, 1.6));
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1.0;
        scene = new THREE.Scene();
        environment = reflectionMap(renderer);
        scene.environment = environment.texture;
        scene.add(new THREE.HemisphereLight(0xf2f6ff, 0x374762, 0.85));
        for (const [x, y, z, color, strength] of [
          [-220, 170, 140, 0xfff3e7, 3.8],
          [180, 220, -210, 0x83abf4, 4.65],
          [100, -190, 200, 0xa9c7f7, 0.8],
        ]) {
          const light = new THREE.DirectionalLight(color, strength);
          light.position.set(x, y, z);
          scene.add(light);
        }
        ({ moving, rotors, envelopes } = createModel(scene));
        ({ forces, power } = makeExplanations(scene));
        drive=createDrive(scene,shafts);
        syncControls();
        camera = new THREE.PerspectiveCamera(32, 1, 1, 2500);
        renderer.domElement.setAttribute("role", "img");
        renderer.domElement.setAttribute("aria-label", fallback.alt);
        renderer.domElement.hidden = true;
        Object.assign(renderer.domElement.style, { width: "100%", height: "100%" });
        host.append(renderer.domElement);
        listen(renderer.domElement, "webglcontextlost", (event) => {
          event.preventDefault();
          if (!lost && renderer) showPoster();
        });
      } catch {
        showPoster();
        return;
      }
    }
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    poses=chapters.map((_,i)=>pose(i));
    schedule();
  }

  function select(p) {
    if(lost)return;
    requested=clamp(p,0,6);
    chapter=chapters[Math.round(requested)];
    syncControls();
    schedule();
  }
  listen(range,"input",()=>{
    const fraction=(Number(range.value)-rangeMin)/(rangeMax-rangeMin);
    if(fraction>0)explodedAmount=fraction;
    if(camera)poses[6]=pose(6);
    select(fraction ? 6 : 3);
  });
  listen(cut,"input",()=>{
    const fraction=Number(cut.value)/100;
    select(1+fraction);
  });
  listen(speed,"input",()=>{syncControls();schedule();});
  listen(motion,"change",()=>{stopFrame();cameraTime=0;schedule();});
  function selectChapter(name) {
    const i=chapters.indexOf(name);
    if(i<0)return;

    select(i);
  }
  for (const element of marker) {
    listen(element, "click", (event) => {
      if (!element.matches(interactiveChapter) && event.target !== element) return;
      if (element.matches("a")) event.preventDefault();
      selectChapter(element.dataset.presentationChapter);
    });
    if (element.matches("[role=button]:not(button)")) listen(element, "keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      selectChapter(element.dataset.presentationChapter);
    });
  }
  const viewport = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting && entry.intersectionRatio > 0;
    if (visible) {
      if (!renderer) resize();
      schedule();
    } else stopFrame();
  }, { threshold: [0,.001], rootMargin: "-"+(root.querySelector(".product-header")?.offsetHeight ?? 0)+"px 0px 0px" });
  viewport.observe(host);
  const sections=marker.filter(el=>!el.matches(interactiveChapter) && chapters.includes(el.dataset.presentationChapter));
  let pendingScroll=0;
  function readScroll(){
    pendingScroll=0;
    if(!sections.length || lost)return;
    const line=innerHeight*.52;
    const stops=sections.map(el=>{
      const rect=el.getBoundingClientRect();
      return {center:rect.top+rect.height*.5, index:chapters.indexOf(el.dataset.presentationChapter)};
    });
    let p=stops[0].index;
    for(let i=1;i<stops.length;i++){
      if(line<=stops[i-1].center)break;
      p=lerp(stops[i-1].index,stops[i].index,clamp((line-stops[i-1].center)/(stops[i].center-stops[i-1].center || 1),0,1));
    }
    select(p);
  }
  listen(window,"scroll",()=>{
    if(!pendingScroll && !lost)pendingScroll=requestAnimationFrame(readScroll);
  });
  if(scrollY>0)readScroll();
  const observer = new ResizeObserver(resize);
  observer.observe(host);
  listen(document, "visibilitychange", () => {
    if (document.hidden) stopFrame();
    else schedule();
  });
  syncControls();
  for(const control of [range,speed,cut])if(control)control.disabled=false;

  return () => {
    events.abort();
    viewport.disconnect();
    cancelAnimationFrame(pendingScroll);
    observer.disconnect();
    disposeRenderer();
    fallback.remove();
    detail.remove();
    chapterControls.remove();
    for(const control of [range,speed,cut])if(control)control.disabled=false;
    for(const el of marker)if(el.matches("button"))el.disabled=false;
    delete root.dataset.presentationState;

    delete host.dataset.presentationFallback;
    for (const element of marker) element.removeAttribute("data-presentation-active");
  };
}
