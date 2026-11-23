import * as THREE from "three";

// Demonstration equipment. The shafts supplied by the calculated model establish
// the two coupling centres, contact planes and the direction of roller rotation.
export function createDrive(scene, shafts) {
  const input = shafts[0], output = shafts.at(-1);
  const motor = new THREE.Group(), bed = new THREE.Group();
  motor.position.set(input.x, input.y, input.min);
  bed.position.set(output.x, output.y, output.max);
  const shell = [new THREE.Group(), new THREE.Group()];
  scene.add(motor, bed, ...shell);

  const metal = (color, roughness = .32, metalness = .72) =>
    new THREE.MeshStandardMaterial({ color, roughness, metalness });
  const iron = metal(0x374858, .4), ribs = metal(0x667784), edge = metal(0xb7c3c6, .25);
  const socket = metal(0x242e39), brass = metal(0xb77842, .29);
  function mesh(parent, geometry, material, x, y, z) {
    const part = new THREE.Mesh(geometry, material);
    part.position.set(x, y, z);
    parent.add(part);
    return part;
  }
  function box(parent, x, y, z, w, h, d, material) {
    return mesh(parent, new THREE.BoxGeometry(w, h, d), material, x, y, z);
  }
  function cylinder(parent, x, y, z, r, length, material, sides = 40) {
    const part = mesh(parent, new THREE.CylinderGeometry(r, r, length, sides), material, x, y, z);
    part.rotation.x = Math.PI / 2;
    return part;
  }
  function bore(shape, x, y, radius) {
    const hole = new THREE.Path();
    hole.absarc(x, y, radius, 0, Math.PI * 2, true);
    shape.holes.push(hole);
  }
  function plate(parent, shape, z, depth, material, bevel = .75) {
    return mesh(parent, new THREE.ExtrudeGeometry(shape, {
      depth, bevelEnabled: !!bevel, bevelSegments: 2, bevelSize: bevel,
      bevelThickness: bevel, curveSegments: 16, steps: 1,
    }), material, 0, 0, z);
  }
  function ring(parent, x, y, z, outer, inner, length, material) {
    const shape = new THREE.Shape();
    shape.absarc(x,y,outer,0,2*Math.PI,false);
    bore(shape,x,y,inner);
    return plate(parent,shape,z,length,material,.25);
  }

  // Rounded casting swept around the addendum envelopes. Separate end plates
  // and hollow walls leave a visible interior when the two halves withdraw.
  function outline(margin, Type = THREE.Shape) {
    const shape = new Type();
    const centers = [[0,0,40],[100.3864,0,77],[170.8274,55.0346,67]];
    // Boundary of the convex hull of the three offset circles.
    const points = centers.flatMap(([x,y,r]) => Array.from({length:64}, (_,i) => {
      const a = i * 2*Math.PI/64;
      return new THREE.Vector2(x+(r+margin)*Math.cos(a), y+(r+margin)*Math.sin(a));
    })).sort((a,b) => a.x-b.x || a.y-b.y);
    function half(list) {
      const chain=[];
      for (const p of list) {
        while (chain.length>1) {
          const a=chain.at(-2), b=chain.at(-1);
          if ((b.x-a.x)*(p.y-a.y) > (b.y-a.y)*(p.x-a.x)) break;
          chain.pop();
        }
        chain.push(p);
      }
      return chain.slice(0,-1);
    }
    const perimeter = [...half(points), ...half(points.reverse())];
    shape.moveTo(perimeter[0].x,perimeter[0].y);
    for (const p of perimeter.slice(1)) shape.lineTo(p.x,p.y);
    shape.closePath();
    return shape;
  }
  function castingWall(parent, z, depth, margin, inner, material) {
    const shape = outline(margin);
    shape.holes.push(outline(inner, THREE.Path));
    plate(parent,shape,z,depth,material);
  }
  const rear = -44, front = 100, seam = 25;
  for (const [side, parent] of shell.entries()) {
    const face = side ? front-4 : rear;
    castingWall(parent,side ? seam : rear,side ? front-seam : seam-rear,2,-2,iron);
    castingWall(parent,side ? seam+.4 : seam-4.4,4,6,-2,ribs);
    for (const z of (side ? [54,81] : [-24,-4])) castingWall(parent,z,2,3.6,.4,ribs);
    // Two anchoring pads follow each casting half at its lowest bearing pocket.
    for(const x of [77,124]) {
      box(parent,x,-73,side ? 80 : -28,15,15,19,iron);
      box(parent,x,-80,side ? 80 : -28,23,3.5,27,ribs);
    }
    const faceShape = outline(2);
    for (const shaft of shafts) {
      if (shaft.min >= face+4 || shaft.max <= face) continue;
      bore(faceShape,shaft.x,shaft.y,16.5);
      ring(parent,shaft.x,shaft.y,side ? front+.4 : rear-3.4,21,16.5,3,edge);
    }
    // Open inspection ports expose both actual gear planes.
    for (const [x,y,r] of [[54,-1,26],[131,38,22]]) {
      bore(faceShape,x,y,r);
      ring(parent,x,y,side ? front+.3 : rear-2.3,r+3,r,2,ribs);
    }
    plate(parent,faceShape,face,4,iron);
    for(const [x,y,tilt] of [[89,-38,-.26],[169,90,.04],[21,10,-.94]]) {
      const rib=box(parent,x,y,side ? front+.9 : rear-.9,3,24,2,ribs);
      rib.rotation.z=tilt;
    }
    for (const [x,y] of [[-26,-15],[11,29],[88,-66],[154,-40],[222,51],[172,111],[97,65]]) {
      cylinder(parent,x,y,side ? front+2 : rear-2,2.9,3,edge,6);
    }
  }

  cylinder(motor,0,0,-73,30,65,iron);
  for (const [z,r,w,mat] of [[-111,27,12,socket],[-102,32,7,ribs],[-43,31,7,ribs],[-37,23,7,iron],[-31,13,6,edge]]) {
    cylinder(motor,0,0,z,r,w,mat);
  }
  for (let i=0;i<22;i++) {
    const a=i*2*Math.PI/22;
    const fin=box(motor,31*Math.cos(a),31*Math.sin(a),-72,5,1.7,53,ribs);
    fin.rotation.z=a;
  }
  box(motor,0,32,-68,22,12,25,socket);
  box(motor,0,39,-68,25,3,28,ribs);
  for (const x of [-19,19]) {
    box(motor,x,-29,-73,9,16,47,iron);
    box(motor,x,-39,-73,17,4,62,ribs);
  }
  box(motor,0,-60,-73,57,36,78,iron);
  box(motor,0,-79,-73,65,4,86,ribs);
  // Each flange pair touches at the calculated shaft end. The outer half and
  // its attached shaft translate together, with opposite withdrawal directions.
  const hubs = [];
  function coupling(shaft, end, direction, peripheral) {
    const fixed = new THREE.Group(), mate = new THREE.Group();
    fixed.position.set(shaft.x,shaft.y,end);
    scene.add(fixed);
    peripheral.add(mate);
    for (const [parent, sign] of [[fixed,-direction],[mate,direction]]) {
      cylinder(parent,0,0,sign*6,12,10,ribs);
      cylinder(parent,0,0,sign*2,15,4,edge);
      for (let i=0;i<6;i++) {
        const a=i*Math.PI/3;
        cylinder(parent,11.5*Math.cos(a),11.5*Math.sin(a),sign*4.8,1.65,1.6,brass,6);
      }
    }
    hubs.push(fixed,mate);
    return fixed;
  }
  coupling(input,input.min,-1,motor);
  coupling(output,output.max,1,bed);
  cylinder(motor,0,0,-20,8,26,edge);
  const rollY=0, rollZ=57, radius=9, spacing=21, rollerCount=8;
  const rollers=[];
  for(let i=0;i<rollerCount;i++){
    const roll = new THREE.Group();
    roll.position.set(i*spacing,rollY,rollZ);
    bed.add(roll);
    cylinder(roll,0,0,0,radius,61,edge);
    cylinder(roll,0,0,0,4.5,72,ribs);
    cylinder(roll,0,0,37,6.7,4,brass);
    rollers.push(roll);
    for (const z of [22,92]) box(bed,i*spacing,-1,z,11,9,4,socket);
  }
  cylinder(bed,0,0,18,6,26,edge);
  const length=(rollerCount-1)*spacing;
  for (const z of [22,92]) {
    box(bed,length/2,-10,z,length+19,9,5,iron);
    box(bed,length/2,-5,z,length+19,2,7,ribs);
    for(const x of [6,length-6]){
      box(bed,x,-70,z,5,116,5,ribs);
      box(bed,x,-130,z,13,4,13,iron);
    }
  }
  // Covered common roller transmission on the outboard side of the conveyor.
  box(bed,length/2,0,96,length+14,16,4,iron);
  const billetLength=68, repeat=length+9;
  const clip = [new THREE.Plane(new THREE.Vector3(1,0,0),-(output.x-8)),
    new THREE.Plane(new THREE.Vector3(-1,0,0),output.x+length+8)];
  const skin = document.createElement("canvas");
  skin.width=128; skin.height=32;
  const ctx=skin.getContext("2d");
  const glow=ctx.createLinearGradient(0,0,0,32);
  glow.addColorStop(0,"#ab3510"); glow.addColorStop(.2,"#ff911e");
  glow.addColorStop(.5,"#ffd55e"); glow.addColorStop(.9,"#ff871f"); glow.addColorStop(1,"#ca4510");
  ctx.fillStyle=glow;ctx.fillRect(0,0,128,32);
  let seed=113;
  const rand=()=>((seed=(1664525*seed+1013904223)>>>0)/4294967296);
  for(let i=0;i<180;i++){
    ctx.fillStyle="rgba(88,23,9,"+(.06+rand()*.32)+")";
    ctx.fillRect(rand()*128,rand()*32,1+rand()*7,1+rand()*2);
  }
  const texture=new THREE.CanvasTexture(skin);
  texture.colorSpace=THREE.SRGBColorSpace;
  const hot=new THREE.MeshStandardMaterial({color:0xffaa5e,map:texture,emissive:0xff9b50,emissiveMap:texture,
    emissiveIntensity:1.6,metalness:.08,roughness:.82,clippingPlanes:clip});
  const billets=[0,1,2].map(()=>box(bed,0,radius+5,rollZ,billetLength,10,23,hot));
  const light=new THREE.PointLight(0xff781e,950,100,2);
  bed.add(light);

  // Contact shadows stay on the floor as peripherals disengage.
  const floorY=-82;
  const shade=document.createElement("canvas");shade.width=shade.height=64;
  const paint=shade.getContext("2d"),fade=paint.createRadialGradient(32,32,0,32,32,32);
  fade.addColorStop(0,"rgba(0,0,0,.67)");fade.addColorStop(.55,"rgba(0,0,0,.34)");fade.addColorStop(1,"transparent");
  paint.fillStyle=fade;paint.fillRect(0,0,64,64);
  const shadowTexture=new THREE.CanvasTexture(shade);
  const ground=new THREE.Group();
  scene.add(ground);
  function shadow(x,z,w,d) {
    const part=mesh(ground,new THREE.PlaneGeometry(w,d),
      new THREE.MeshBasicMaterial({map:shadowTexture,transparent:true,depthWrite:false}),x,floorY,z);
    part.rotation.x=-Math.PI/2;return part;
  }
  shadow(95,25,350,230);
  const motorShadow=shadow(input.x,input.min-73,118,160), loadShadow=shadow(output.x+length/2,output.max+rollZ,240,140);
  const frameBoxes=[motor,bed,...shell].map(p=>new THREE.Box3().setFromObject(p));
  const outward=[new THREE.Vector3(0,0,-130),new THREE.Vector3(0,0,130),
    new THREE.Vector3(0,0,-105),new THREE.Vector3(0,0,105)];
  const materials=new Set();
  for(const parent of [motor,bed,...shell,hubs[0],hubs[2],ground])
    parent.traverse(p=>{if(p.material) materials.add(p.material);});
  let opacity=1;

  return {
    frameBoxes,outward,
    update(detach,cut,visibility,angles) {
      motor.position.z=input.min-130*detach;bed.position.z=output.max+130*detach;
      shell[0].position.z=-105*cut;shell[1].position.z=105*cut;
      // Withdraw the peripherals from view before the tight gear shot.
      for(const part of [motor,bed,...shell,hubs[0],hubs[2],ground]) part.visible=visibility>.001;
      if(visibility!==opacity){
        for(const mat of materials){
          const blended=visibility<1 || mat.map===shadowTexture;
          if(mat.transparent!==blended){mat.transparent=blended;mat.needsUpdate=true;}
          mat.depthWrite=!blended;mat.opacity=visibility;
        }
        opacity=visibility;
      }
      motorShadow.position.z=motor.position.z-73;loadShadow.position.z=bed.position.z+rollZ;
      // Keep coupling clocking continuous through a reversible inspection.
      const transportAngle=angles[2];
      hubs[0].rotation.z=hubs[1].rotation.z=angles[0];
      hubs[2].rotation.z=angles[2];hubs[3].rotation.z=transportAngle;
      for(const roll of rollers)roll.rotation.z=transportAngle;
      const travel=THREE.MathUtils.euclideanModulo(radius*transportAngle,repeat);
      billets.forEach((part,i)=>{part.position.x=length*.56-travel+(i-1)*repeat;});
      light.position.set(THREE.MathUtils.clamp(billets[1].position.x,0,length),radius+16,rollZ);
    },
    dispose(){texture.dispose();shadowTexture.dispose();},
  };
}
