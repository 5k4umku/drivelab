import { prepareSceneEffects } from "./scene-effects.js";
import * as THREE from "three";
import { GearViewer, gearGeometry, sceneAccent, steelMaterial } from "./viewer.js";

const selectedSteel = new THREE.Color(0xb6b8bb).lerp(new THREE.Color(sceneAccent), 0.55);

export class AssemblyViewer extends GearViewer {
  update(result, activeStage = 0) {
    this.result = result;
    this.activeStage = Number.isInteger(activeStage) && result.stages[activeStage] ? activeStage : 0;
    this.theta = 0;
    for (const child of [...this.model.children]) {
      this.model.remove(child);
      child.traverse((o) => {
        o.geometry?.dispose();
        o.material?.dispose();
      });
    }
    this.rotors = [];
    for (const shaft of result.shafts) {
      const rotor = new THREE.Group();
      rotor.position.set(shaft.x, shaft.y, 0);
      this.model.add(rotor);
      this.rotors.push(rotor);
      const body = new THREE.Mesh(
        new THREE.CylinderGeometry(
          shaft.diameter / 2,
          shaft.diameter / 2,
          shaft.zMax - shaft.zMin,
          24,
        ),
        steelMaterial(0x85888e),
      );
      body.rotation.x = Math.PI / 2;
      body.position.z = (shaft.zMax + shaft.zMin) / 2;
      rotor.add(body);
      for (const name of ["A", "B"]) {
        const support = new THREE.Mesh(
          new THREE.TorusGeometry(
            shaft.diameter * 0.78,
            shaft.diameter * 0.23,
            8,
            28,
          ),
          // Polished fixed rings remain distinct from the darker floating rings.
          steelMaterial(name === shaft.locating ? 0xe3e3e1 : 0x686a70),
        );
        support.position.set(shaft.x, shaft.y, shaft[name].z);
        this.model.add(support);
        if (shaft.bearing === "roller") {
          const collar = new THREE.Mesh(
            new THREE.TorusGeometry(
              shaft.diameter * 0.8,
              shaft.diameter * 0.1,
              4,
              28,
            ),
            steelMaterial(0xbfc0c3),
          );
          collar.position.set(
            shaft.x,
            shaft.y,
            shaft[name].z + shaft.diameter * 0.22,
          );
          this.model.add(collar);
        }
      }
    }
    for (const gear of result.gears) {
      const stage = result.stages[gear.stage];
      const c = stage.result.chosen;
      const mesh = new THREE.Mesh(
        gearGeometry(
          c,
          gear.side,
          gear.width,
          stage.result.input.gearType,
          stage.hand === "left" ? -1 : 1,
        ),
        steelMaterial(gear.stage === this.activeStage ? selectedSteel : 0x96999e),
      );
      mesh.position.z = gear.z;
      mesh.userData.explodeDirection = new THREE.Vector3(
        0,
        0,
        (gear.side === 1 ? -1 : 1) * (gear.stage + 1) * gear.width * 2,
      );
      mesh.rotation.z =
        (stage.angle * Math.PI) / 180 +
        (gear.side === 2
          ? Math.PI - Math.PI / c.z2
          : c.meshType === "internal"
            ? Math.PI
            : 0);
      this.rotors[gear.shaft].add(mesh);
    }
    if (result.motor) {
      const s = result.shafts[0],
        m = result.motor,
        r = m.frame * 0.78,
        length = m.frame * 2.4,
        z = s.zMin - length / 2 - 25;
      const body = new THREE.Mesh(
        new THREE.CylinderGeometry(r, r, length, 32),
        steelMaterial(0x74767b),
      );
      body.rotation.x = Math.PI / 2;
      body.position.set(s.x, s.y, z);
      this.model.add(body);
      for (let i = 0; i < 10; i++) {
        const rib = new THREE.Mesh(
          new THREE.TorusGeometry(r + 2, 2, 4, 32),
          steelMaterial(0xa1a3a5),
        );
        rib.position.set(s.x, s.y, z - length * 0.4 + (length * 0.8 * i) / 9);
        this.model.add(rib);
      }
      const feet = new THREE.Mesh(
        new THREE.BoxGeometry(r * 2.1, 10, length * 0.7),
        steelMaterial(0x64666b),
      );
      feet.position.set(s.x, s.y - r, z);
      this.model.add(feet);
      const coupling = new THREE.Mesh(
        new THREE.CylinderGeometry(s.diameter * 0.8, s.diameter * 0.8, 35, 20),
        steelMaterial(0xafb0b2),
      );
      coupling.rotation.x = Math.PI / 2;
      coupling.position.z = s.zMin - 12;
      this.rotors[0].add(coupling);
    }
    const b = result.bounds,
      clearance = result.project.housing?.clearance ?? 20,
      mode = result.project.housing?.mode ?? "contour";
    // A visible housing can extend well beyond a compact gear train.
    const cameraBounds = b.map((value, i) =>
      mode === "hidden" ? value : value + (i % 2 ? clearance : -clearance),
    );
    if (result.motor) {
      const s = result.shafts[0],
        m = result.motor;
      cameraBounds[4] = Math.min(cameraBounds[4], s.zMin - m.frame * 2.4 - 25);
      cameraBounds[0] = Math.min(cameraBounds[0], s.x - m.frame);
      cameraBounds[1] = Math.max(cameraBounds[1], s.x + m.frame);
      cameraBounds[2] = Math.min(cameraBounds[2], s.y - m.frame);
      cameraBounds[3] = Math.max(cameraBounds[3], s.y + m.frame);
    }
    this.center = new THREE.Vector3(
      (cameraBounds[0] + cameraBounds[1]) / 2,
      (cameraBounds[2] + cameraBounds[3]) / 2,
      (cameraBounds[4] + cameraBounds[5]) / 2,
    );
    this.extent = Math.max(
      cameraBounds[1] - cameraBounds[0],
      cameraBounds[3] - cameraBounds[2],
      cameraBounds[5] - cameraBounds[4],
      100,
    );
    const box = new THREE.BoxGeometry(
      b[1] - b[0] + 2 * clearance,
      b[3] - b[2] + 2 * clearance,
      b[5] - b[4] + 2 * clearance,
    );
    const housingCenter = new THREE.Vector3(
      (b[0] + b[1]) / 2,
      (b[2] + b[3]) / 2,
      (b[4] + b[5]) / 2,
    );
    if (mode === "transparent") {
      const shell = new THREE.Mesh(
        box.clone(),
        new THREE.MeshStandardMaterial({
          color: 0xb8bcc2,
          transparent: true,
          opacity: 0.1,
          depthWrite: false,
          side: THREE.DoubleSide,
        }),
      );
      shell.position.copy(housingCenter);
      this.model.add(shell);
    }
    this.envelope = new THREE.LineSegments(
      new THREE.EdgesGeometry(box),
      new THREE.LineBasicMaterial({
        color: 0xb1b5be,
        transparent: true,
        opacity: 0.25,
      }),
    );
    box.dispose();
    this.envelope.position.copy(housingCenter);
    this.envelope.visible = mode !== "hidden" && (this.showEnvelope ?? true);
    this.model.add(this.envelope);
    prepareSceneEffects(this);
    this.view(this.viewMode || "iso", true);
    this.resize();
  }
  contactDetail() {
    const stage = this.result?.stages[this.activeStage];
    const pinion = this.result?.gears.find((gear) => gear.stage === stage?.index && gear.side === 1);
    if (!stage?.result.chosen || !pinion) return null;
    // The calculated offset points toward the wheel for an external mesh
    // and away from its axis for an internal mesh.
    return {
      pair: stage.result,
      number: stage.index + 1,
      position: new THREE.Vector3(
        pinion.x + pinion.offset[0],
        pinion.y + pinion.offset[1],
        pinion.z,
      ),
    };
  }
  animate(now) {
    const dt = Math.max(0, (now - this.last) / 1000);
    this.last = now;
    if (this.result && this.playing && !document.hidden && this.inViewport) {
      const step = (dt * this.scale * 2 * Math.PI) / 60;
      for (let i = 0; i < this.rotors.length; i++)
        this.rotors[i].rotation.z =
          (this.rotors[i].rotation.z + step * this.result.shafts[i].signedSpeed) %
          (2 * Math.PI);
    }
    this.tickEffects(dt);
    this.controls.update(dt);
    if (!document.hidden && this.inViewport)
      this.renderer.render(this.scene, this.camera);
    requestAnimationFrame(this.animate);
  }
}
