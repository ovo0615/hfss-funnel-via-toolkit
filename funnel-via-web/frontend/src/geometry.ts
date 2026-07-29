// 此範本由虎門科技資深技術工程師 Jeff Hong 洪敬傑提供。
export type Vec3 = [number, number, number];

export const COLORS = {
  copper: 0xb87333,
  airbox: 0x5aa0ff,
};

export type Prim =
  | { kind: "cone"; p0: Vec3; p1: Vec3; r0: number; r1: number; color: number; opacity?: number }
  | { kind: "cylinder"; p0: Vec3; p1: Vec3; radius: number; color: number; opacity?: number };

export interface Bounds { min: Vec3; max: Vec3 }
export interface Scene {
  prims: Prim[];
  bounds: Bounds;
  fitBounds: Bounds;
}

export interface SegConfig {
  drill: number;
  finish: number;
  changes: string; // "1,2\n2,3"
}

// 簡單的 parse changes，不包含個別 width 覆蓋的邏輯（因為預覽通常只看形狀，我們可以簡化）
function parseChanges(text: string) {
  const lines = text.split('\n');
  const changes: [number, number, number | null, number | null][] = [];
  for (const line of lines) {
    const l = line.trim();
    if (!l || l.startsWith('#')) continue;
    const parts = l.split(',').map(x => x.trim());
    if (parts.length >= 4) {
      changes.push([parseInt(parts[0]), parseInt(parts[1]), parseFloat(parts[2]), parseFloat(parts[3])]);
    } else if (parts.length >= 2) {
      changes.push([parseInt(parts[0]), parseInt(parts[1]), null, null]);
    }
  }
  return changes;
}

function boundsOfPoints(points: Vec3[]): Bounds {
  const min: Vec3 = [Infinity, Infinity, Infinity];
  const max: Vec3 = [-Infinity, -Infinity, -Infinity];
  for (const p of points) {
    for (let i = 0; i < 3; i++) {
      if (p[i] < min[i]) min[i] = p[i];
      if (p[i] > max[i]) max[i] = p[i];
    }
  }
  return { min, max };
}

function padBounds(b: Bounds, pad: number): Bounds {
  if (!isFinite(b.min[0])) return b;
  return {
    min: [b.min[0] - pad, b.min[1] - pad, b.min[2] - pad],
    max: [b.max[0] + pad, b.max[1] + pad, b.max[2] + pad],
  };
}

export function buildScene(cfg: SegConfig): Scene | null {
  try {
    const drill = cfg.drill;
    const finish = cfg.finish;
    if (isNaN(drill) || isNaN(finish) || drill <= 0 || finish <= 0) return null;
    
    const changes = parseChanges(cfg.changes);
    if (changes.length === 0) return null;
    
    // 預覽: 我們沒有真實層 Z, 就假設每段高度固定為 3 mil，純展示用
    const segH = 3.0;
    
    const prims: Prim[] = [];
    const points: Vec3[] = [];
    
    // Z=0 is top, going down
    let currentZ = 0;
    
    for (const [, , d, f] of changes) {
      const topRad = (d !== null ? d : drill) / 2;
      const botRad = (f !== null ? f : finish) / 2;
      
      const p0: Vec3 = [0, 0, currentZ];
      const p1: Vec3 = [0, 0, currentZ - segH];
      
      prims.push({
        kind: "cone",
        p0, p1,
        r0: topRad,
        r1: botRad,
        color: COLORS.copper
      });
      
      points.push([topRad, 0, currentZ]);
      points.push([-topRad, 0, currentZ]);
      points.push([botRad, 0, currentZ - segH]);
      points.push([-botRad, 0, currentZ - segH]);
      
      currentZ -= segH;
    }
    
    const bounds = boundsOfPoints(points);
    const fitBounds = padBounds(bounds, drill);
    
    return { prims, bounds, fitBounds };
  } catch {
    return null;
  }
}
