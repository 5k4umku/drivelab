import * as THREE from "three";

const tau = 2 * Math.PI;

// t is the length unwound from the base circle divided by its radius.
function roll(radius, base) {
  return Math.sqrt(Math.max(0, (radius / base - 1) * (radius / base + 1)));
}

function section(c, side) {
  const z = c["z" + side], pitch = tau / z;
  const reference = c["d" + side] / 2, base = c["db" + side] / 2;
  const working = (c["dw" + side] ?? c["d" + side]) / 2;
  const tip = c["da" + side] / 2;
  let root = c["df" + side] / 2;
  const ring = c.meshType === "internal" && side === 2;
  const beta = c.beta * Math.PI / 180;
  const tReference = roll(reference, base);
  const invReference = tReference - Math.atan(tReference);
  // tan(alpha_n) = tan(alpha_t) cos(beta). Internal shifts are excluded by Python.
  const half = (Math.PI / 2 + 2 * (c["x" + side] ?? 0) * tReference * Math.cos(beta)) / z;
  const halfAngle = t => half + (ring ? -1 : 1) * (invReference - (t - Math.atan(t)));
  // On a small ring the two mathematically extended flanks can meet before df.
  // Stop at the tooth-space bisector; the remaining transition needs cutter data.
  const limitedRoot = ring && halfAngle(roll(root, base)) >= pitch / 2;
  if (limitedRoot) {
    let lo = reference, hi = root;
    for (let j = 0; j < 54; j++) {
      const r = (lo + hi) / 2;
      if (halfAngle(roll(r, base)) < pitch / 2) lo = r;
      else hi = r;
    }
    root = (lo + hi) / 2;
  }
  return { z, pitch, reference, base, working, tip, root, ring, beta, halfAngle, limitedRoot };
}

// Loaded flank at the pitch point in the middle plane. For internal gears the
// two radius vectors are parallel, so opposite angular flanks meet there.
export function meshPhase(c, side, direction = 0, drivingSign = 1) {
  const s = section(c, side);
  const ray = side === 2 || c.meshType === "internal" ? Math.PI : 0;
  return direction + ray - (s.ring ? -1 : 1) * Math.sign(drivingSign) * s.halfAngle(roll(s.working, s.base));
}

function polar(radius, angle) {
  return new THREE.Vector2(radius * Math.cos(angle), radius * Math.sin(angle));
}

function arc(radius, from, to, count) {
  return Array.from({ length: count + 1 }, (_, i) => polar(radius, from + (to - from) * i / count));
}

function toothStrips(s, module) {
  const { base, tip, root, ring, pitch, halfAngle } = s;
  const start = Math.max(base, Math.min(tip, root));
  const end = Math.max(tip, root);
  const low = roll(start, base), high = roll(end, base);
  // In roll coordinates |P''(t)| = r. This bounds linear chord error on the flank.
  const step = Math.sqrt(8 * .001 * module / end);
  const knots = [low, ...[s.reference, s.working].filter(r => r > start && r < end)
    .map(r => roll(r, base)), high].sort((a, b) => a - b);
  const flank = [polar(start, -halfAngle(low))];
  for (let k = 1; k < knots.length; k++) {
    const span = knots[k] - knots[k - 1];
    if (span < 1e-12) continue;
    const n = Math.ceil(span / step);
    for (let j = 1; j <= n; j++) {
      const t = knots[k - 1] + span * j / n;
      flank.push(polar(base * Math.hypot(1, t), -halfAngle(t)));
    }
  }
  if (ring) flank.reverse();
  const rootAngle = halfAngle(roll(root, base));
  const tipAngle = halfAngle(roll(tip, base));
  const strips = s.limitedRoot ? [] : [arc(root, -pitch / 2, -rootAngle, 3)];
  if (root < base) strips.push([polar(root, -rootAngle), flank[0]]);
  strips.push(flank, arc(tip, -tipAngle, tipAngle, 6));
  for (const strip of strips.slice(0, -1).reverse()) {
    strips.push(strip.slice().reverse().map(p => new THREE.Vector2(p.x, -p.y)));
  }
  return strips;
}

export function gearGeometry(c, side, width, type, hand = 1, sectors = c["z" + side]) {
  const s = section(c, side);
  const strips = toothStrips(s, c.m);
  // Independently indexed strips keep the tip edges, end faces and chevron seam sharp.
  const boundary = strips.flatMap(strip => strip.slice(0, -1));
  boundary.push(strips.at(-1).at(-1));
  const outer = s.ring ? arc(c.outerDiameter / 2, -s.pitch / 2, s.pitch / 2, 6) : [];
  const cap = s.ring ? [...outer, ...boundary.slice().reverse()] : [new THREE.Vector2(), ...boundary];
  const faces = THREE.ShapeUtils.triangulateShape(cap, []);
  const twist = type === "spur" ? 0 : hand * (side === 2 && !s.ring ? -1 : 1) * Math.tan(s.beta) / s.reference;
  const chevron = type === "herringbone";
  const halfWidth = width / 2;
  const maxRadius = Math.max(s.tip, s.root, s.ring ? c.outerDiameter / 2 : 0);
  const maxAngle = Math.sqrt(.032 * c.m / maxRadius);
  const halfLayers = Math.max(1, Math.ceil(halfWidth * Math.abs(twist) / maxAngle));
  const positions = [], indices = [];
  function vertex(p, angle, depth) {
    const co = Math.cos(angle), si = Math.sin(angle);
    positions.push(co * p.x - si * p.y, si * p.x + co * p.y, depth);
  }
  // On a chevron the specified hand describes the positive-Z half.
  function angleAt(center, depth) {
    return center + (chevron ? Math.abs(depth) : depth) * twist;
  }
  function wall(strip, center, from, to, layers, inward) {
    const offset = positions.length / 3, stride = strip.length;
    for (let l = 0; l <= layers; l++) {
      const depth = from + (to - from) * l / layers;
      for (const p of strip) vertex(p, angleAt(center, depth), depth);
    }
    for (let l = 0; l < layers; l++)
      for (let j = 1; j < stride; j++) {
        const a = offset + l * stride + j - 1, b = a + 1;
        if (inward) indices.push(a, b + stride, b, a, a + stride, b + stride);
        else indices.push(a, b, b + stride, a, b + stride, a + stride);
      }
  }
  for (let i = 0; i < sectors; i++) {
    const center = i * s.pitch;
    for (const strip of (s.ring ? [...strips, outer] : strips)) {
      const inward = s.ring && strip !== outer;
      if (chevron) {
        wall(strip, center, -halfWidth, 0, halfLayers, inward);
        wall(strip, center, 0, halfWidth, halfLayers, inward);
      } else wall(strip, center, -halfWidth, halfWidth, twist ? 2 * halfLayers : 1, inward);
    }
    for (const depth of [-halfWidth, halfWidth]) {
      const offset = positions.length / 3;
      for (const p of cap) vertex(p, angleAt(center, depth), depth);
      for (const [a, b, d] of faces) {
        if (depth > 0) indices.push(offset + a, offset + b, offset + d);
        else indices.push(offset + d, offset + b, offset + a);
      }
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  geometry.userData.limitedRingRoot = s.limitedRoot;
  return geometry;
}

// Long helices or large tooth counts can otherwise duplicate millions of vertices.
// The repeated sector includes both end faces and is rotated by the exact tooth pitch.
export function gearMesh(c, side, width, type, hand, material) {
  const teeth = c["z" + side];
  if (teeth <= 256 && width <= 160 * c.m)
    return new THREE.Mesh(gearGeometry(c, side, width, type, hand), material);
  const mesh = new THREE.InstancedMesh(gearGeometry(c, side, width, type, hand, 1), material, teeth);
  const rotation = new THREE.Matrix4();
  for (let i = 0; i < teeth; i++) mesh.setMatrixAt(i, rotation.makeRotationZ(i * tau / teeth));
  return mesh;
}
