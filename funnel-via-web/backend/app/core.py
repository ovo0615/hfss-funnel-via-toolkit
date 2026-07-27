# -*- coding: utf-8 -*-
# =====================================================================
# HFSS 3D 漏斗狀建模工具 ── 核心邏輯 (無 GUI 依賴)
# 此工具由虎門科技資深技術工程師 Jeff Hong 洪敬傑提供
# =====================================================================

import re

# =====================================================================
#  解析函式
# =====================================================================
def parse_stackup(text):
    """回傳 (copper_top_z, copper_bot_z)。"""
    copper_top_z, copper_bot_z = {}, {}
    z = 0.0
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue
        kind, name, thickness = parts[0], parts[1], float(parts[2])
        z_top, z_bot = z, z - thickness
        if kind == "copper" and len(parts) >= 4:
            layer = int(parts[3])
            copper_top_z[layer] = z_top
            copper_bot_z[layer] = z_bot
        z = z_bot
    return copper_top_z, copper_bot_z

def parse_changes(text):
    """回傳 [(start, end, drill_or_None, finish_or_None), ...]。"""
    changes = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        p = [x.strip() for x in line.split(",")]
        if len(p) >= 4:
            changes.append((int(p[0]), int(p[1]), float(p[2]), float(p[3])))
        elif len(p) >= 2:
            changes.append((int(p[0]), int(p[1]), None, None))
    return changes

def parse_coords(text):
    """回傳 [(x, y), ...]。"""
    coords = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        p = [x.strip() for x in line.split(",")]
        if len(p) >= 2:
            coords.append((float(p[0]), float(p[1])))
    return coords

# 厚度單位 → mil 換算
UNIT2MIL = {"meter": 39370.0787, "m": 39370.0787, "cm": 393.700787,
            "mm": 39.3700787, "um": 0.0393700787, "micron": 0.0393700787,
            "nm": 3.93700787e-5, "mil": 1.0, "in": 1000.0, "inch": 1000.0}

def val_to_mil(s):
    """把 '0.0001meter' / '5mil' / '0.12mm' 等字串換算成 mil。"""
    m = re.match(r"\s*([-+0-9.eE]+)\s*([a-zA-Z]*)", str(s))
    if not m:
        return None
    val = float(m.group(1))
    unit = (m.group(2) or "meter").lower()
    return val * UNIT2MIL.get(unit, 39370.0787)

def parse_layer_info(infos):
    """GetLayerInfo 回傳 ['Key: Value', ...] → dict。"""
    d = {}
    for it in infos:
        if ": " in it:
            k, v = it.split(": ", 1)
            d[k.strip()] = v.strip()
    return d

def resolve_changes(changes, drill, finish):
    """把 layer change 表中未指定寬度（None）的列，用全域 drill/finish 補上。"""
    out = []
    for s, e, d, f in changes:
        out.append((s, e,
                    d if d is not None else drill,
                    f if f is not None else finish))
    return out

def get_segments(copper_top_z, copper_bot_z, changes):
    """用疊構表算出的『絕對 Z』分段（手動座標模式使用）。"""
    segs = []
    for start, end, drill_d, finish_d in changes:
        z_top = copper_bot_z.get(start, 0)
        z_bot = copper_top_z.get(end, 0)
        segs.append({"z_bottom": z_bot,
                     "height": z_top - z_bot,
                     "r_bottom": finish_d / 2.0,
                     "r_top": drill_d / 2.0})
    return segs

def get_segments_fit(copper_top_z, copper_bot_z, changes, z_top_via, z_bottom_via):
    """以 via 頭尾兩端為錨點，依疊構各銅層的『相對比例』定位每個節點。"""
    if not changes: return []
    layers = [changes[0][0]] + [c[1] for c in changes]
    cz = {L: (copper_top_z.get(L, 0) + copper_bot_z.get(L, 0)) / 2.0 for L in layers}
    s_top, s_bot = cz[layers[0]], cz[layers[-1]]
    span_s = s_top - s_bot
    span_m = z_top_via - z_bottom_via

    def mapz(z):
        if abs(span_s) < 1e-12:
            return z_top_via
        return z_bottom_via + (z - s_bot) / span_s * span_m

    out = []
    for start, end, drill_d, finish_d in changes:
        zt, zb = mapz(cz[start]), mapz(cz[end])
        out.append({"z_bottom": zb, "height": zt - zb,
                    "r_bottom": finish_d / 2.0,
                    "r_top": drill_d / 2.0})
    return out

def get_segments_realz(layout_layer_z, changes, z_top_via, z_bottom_via):
    """最精準：節點直接放在『layout 讀到的真實層 Z』。"""
    if not layout_layer_z or not changes:
        return None
    layers = [changes[0][0]] + [c[1] for c in changes]
    if not all(str(L) in layout_layer_z for L in layers):
        return None
        
    real_top = layout_layer_z[str(layers[0])]["upper"]
    real_bot = layout_layer_z[str(layers[-1])]["lower"]
    off_top = z_top_via - real_top
    off_bot = z_bottom_via - real_bot
    offset = (off_top + off_bot) / 2.0
    residual = off_top - off_bot
    
    out = []
    for start, end, drill_d, finish_d in changes:
        zt = layout_layer_z[str(start)]["center"] + offset
        zb = layout_layer_z[str(end)]["center"] + offset
        out.append({"z_bottom": zb, "height": zt - zb,
                    "r_bottom": finish_d / 2.0,
                    "r_top": drill_d / 2.0})
    return out, offset, residual
