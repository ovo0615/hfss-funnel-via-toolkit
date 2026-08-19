import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { Scene as GeoScene, Prim, Vec3 } from "../geometry";

function v3(p: Vec3): THREE.Vector3 {
  return new THREE.Vector3(p[0], p[1], p[2]);
}

function makeMaterial(color: number, opacity?: number): THREE.Material {
  return new THREE.MeshStandardMaterial({
    color,
    metalness: 0.6,
    roughness: 0.3,
    transparent: opacity !== undefined && opacity < 1,
    opacity: opacity ?? 1,
  });
}

function primToObject(prim: Prim): THREE.Object3D | null {
  switch (prim.kind) {
    case "cone": {
      const a = v3(prim.p0); // top
      const b = v3(prim.p1); // bottom
      // dir 指向上方，這樣 CylinderGeometry 的頂部 (+Y) 就會在 a (top)
      const dir = new THREE.Vector3().subVectors(a, b);
      const len = dir.length();
      if (len < 1e-6) return null;
      // CylinderGeometry(radiusTop, radiusBottom, height, radialSegments)
      const geo = new THREE.CylinderGeometry(prim.r0, prim.r1, len, 32);
      const mesh = new THREE.Mesh(geo, makeMaterial(prim.color, prim.opacity));
      mesh.position.copy(a).add(b).multiplyScalar(0.5);
      
      // align object's up vector (0,1,0) to dir
      mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize());
      
      // 添加金屬線框強化立體感
      const edges = new THREE.EdgesGeometry(geo);
      const line = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({ color: 0x8b4513, opacity: 0.3, transparent: true }));
      mesh.add(line);
      
      return mesh;
    }
    case "cylinder": {
      const a = v3(prim.p0);
      const b = v3(prim.p1);
      const dir = new THREE.Vector3().subVectors(b, a);
      const len = dir.length();
      if (len < 1e-6) return null;
      const geo = new THREE.CylinderGeometry(prim.radius, prim.radius, len, 20);
      const mesh = new THREE.Mesh(geo, makeMaterial(prim.color, prim.opacity));
      mesh.position.copy(a).add(b).multiplyScalar(0.5);
      mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize());
      return mesh;
    }
    default:
      return null;
  }
}

function disposeGroup(group: THREE.Group) {
  group.traverse((obj) => {
    const m = obj as THREE.Mesh;
    if (m.geometry) m.geometry.dispose();
    const mat = m.material;
    if (mat) (Array.isArray(mat) ? mat : [mat]).forEach((x) => x.dispose());
  });
  group.clear();
}

interface Props {
  scene: GeoScene | null;
  fitKey: string;
}

export default function Preview3D({ scene, fitKey }: Props) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const groupRef = useRef<THREE.Group | null>(null);
  const lastFitDiagRef = useRef(0);
  const lastFitKeyRef = useRef("");

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    mount.appendChild(renderer.domElement);

    const sceneThree = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(
      45,
      mount.clientWidth / Math.max(mount.clientHeight, 1),
      0.001,
      100000
    );
    camera.up.set(0, 0, 1); // Z 軸朝上
    camera.position.set(20, -20, 15);
    cameraRef.current = camera;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controlsRef.current = controls;

    sceneThree.add(new THREE.AmbientLight(0xffffff, 0.75));
    const d1 = new THREE.DirectionalLight(0xffffff, 1.0);
    d1.position.set(1, -1, 1.4);
    sceneThree.add(d1);
    const d2 = new THREE.DirectionalLight(0xffffff, 0.6);
    d2.position.set(-1, 1, 0.6);
    sceneThree.add(d2);

    const grid = new THREE.GridHelper(50, 20, 0x555555, 0x222222);
    grid.rotation.x = Math.PI / 2; // 置於 XY 平面
    (grid.material as THREE.Material).transparent = true;
    (grid.material as THREE.Material).opacity = 0.5;
    sceneThree.add(grid);

    const group = new THREE.Group();
    groupRef.current = group;
    sceneThree.add(group);

    let raf = 0;
    const animate = () => {
      raf = requestAnimationFrame(animate);
      controls.update();
      renderer.render(sceneThree, camera);
    };
    animate();

    const ro = new ResizeObserver(() => {
      const w = mount.clientWidth;
      const h = Math.max(mount.clientHeight, 1);
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    });
    ro.observe(mount);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      controls.dispose();
      if (groupRef.current) disposeGroup(groupRef.current);
      renderer.dispose();
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement);
    };
  }, []);

  useEffect(() => {
    const group = groupRef.current;
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!group || !camera || !controls) return;

    disposeGroup(group);
    if (!scene) return;
    for (const prim of scene.prims) {
      const obj = primToObject(prim);
      if (obj) group.add(obj);
    }

    const { min, max } = scene.fitBounds;
    if (!isFinite(min[0])) return;
    
    const center = new THREE.Vector3(
      (min[0] + max[0]) / 2,
      (min[1] + max[1]) / 2,
      (min[2] + max[2]) / 2
    );
    const diag = Math.hypot(max[0] - min[0], max[1] - min[1], max[2] - min[2]);
    const ratio = lastFitDiagRef.current > 0 ? diag / lastFitDiagRef.current : Infinity;
    const drift = center.distanceTo(controls.target);
    const keyChanged = fitKey !== lastFitKeyRef.current;

    if (keyChanged || ratio > 1.4 || ratio < 0.7 || drift > 0.4 * Math.max(diag, 1e-6)) {
      const radius = Math.max(diag / 2, 1e-4);
      const fov = (camera.fov * Math.PI) / 180;
      const fitH = radius / Math.sin(fov / 2);
      const fitW = radius / Math.sin(Math.atan(Math.tan(fov / 2) * camera.aspect));
      const dist = 1.3 * Math.max(fitH, fitW);
      const dir = new THREE.Vector3(1, -1.2, 0.8).normalize();
      camera.position.copy(center).add(dir.multiplyScalar(dist));
      camera.near = Math.max(dist / 1000, 0.0002);
      camera.far = dist * 100;
      camera.updateProjectionMatrix();
      controls.target.copy(center);
      controls.update();
      lastFitDiagRef.current = diag;
      lastFitKeyRef.current = fitKey;
    }
  }, [scene, fitKey]);

  return <div style={{ width: "100%", height: "100%" }} ref={mountRef} />;
}
