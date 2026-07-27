import asyncio
import traceback
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from app.core import (
    parse_stackup, parse_changes, parse_coords, resolve_changes,
    get_segments, get_segments_fit, get_segments_realz,
    parse_layer_info, val_to_mil
)

app = FastAPI(title="Funnel Via Web App")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 狀態管理
class AppState:
    def __init__(self):
        self.hfss = None
        self.layout_layer_z = {}
        self.log_queue = asyncio.Queue()
        self.loop = None

state = AppState()

@app.on_event("startup")
async def startup_event():
    state.loop = asyncio.get_running_loop()

# =====================================================================
# 日誌管理 (WebSocket)
# =====================================================================
def log_msg(msg: str):
    print(msg)
    if state.loop and not state.loop.is_closed():
        try:
            asyncio.run_coroutine_threadsafe(state.log_queue.put(msg), state.loop)
        except Exception:
            pass

@app.websocket("/ws/log")
async def websocket_log(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            msg = await state.log_queue.get()
            await websocket.send_text(msg)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")

# =====================================================================
# API Models
# =====================================================================
class ConnectReq(BaseModel):
    version: str

class ReadStackupResp(BaseModel):
    stackup_text: str
    layout_layer_z: Dict[str, Any]

class GrabReq(BaseModel):
    mode: str  # "selected" or "prefix"
    prefix: str = ""

class BuildReq(BaseModel):
    stackup: str
    changes: str
    coords: str
    src_mode: str  # "grab" or "manual"
    grabbed: List[Dict[str, Any]]
    drill: float
    finish: float
    autodia: bool
    fit: bool
    replace: bool
    layout_layer_z: Dict[str, Any]
    material: str

# =====================================================================
# Endpoints
# =====================================================================
@app.post("/api/connect")
def connect(req: ConnectReq):
    try:
        log_msg(f"連線 AEDT {req.version} 中…")
        from ansys.aedt.core import Hfss
        state.hfss = Hfss(version=req.version, new_desktop=False)
        state.hfss.modeler.model_units = "mil"
        msg = f"已連線：{state.hfss.design_name}"
        log_msg(f"連線成功，目前設計：{state.hfss.design_name}（單位 mil）")
        return {"status": "success", "message": msg, "design_name": state.hfss.design_name}
    except Exception as e:
        err = f"連線失敗：{e}"
        log_msg(f"[錯誤] {err}")
        return {"status": "error", "message": str(e)}

@app.post("/api/release")
def release_aedt():
    try:
        if state.hfss:
            state.hfss.release_desktop(close_projects=False, close_desktop=False)
            state.hfss = None
            msg = "已釋放 AEDT 連線，您現在可以關閉 AEDT 了。"
            log_msg(msg)
            return {"status": "success", "message": msg}
        return {"status": "success", "message": "目前沒有連線"}
    except Exception as e:
        log_msg(f"[錯誤] 釋放連線失敗：{e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/read_stackup", response_model=ReadStackupResp)
def read_stackup():
    if not state.hfss:
        return {"stackup_text": "", "layout_layer_z": {}}
    
    cur_design = getattr(state.hfss, "design_name", None)
    oproject = state.hfss.oproject
    try:
        try:
            design_names = list(state.hfss.design_list)
        except Exception:
            design_names = list(oproject.GetTopDesignList())
        layout_designs = []
        for nm in design_names:
            try:
                odes = oproject.SetActiveDesign(nm)
                if "Layout" in str(odes.GetDesignType()):
                    layout_designs.append(nm)
            except Exception:
                continue
        if not layout_designs:
            log_msg("[錯誤] 專案中找不到 3D Layout 設計，無法讀取疊構。")
            return {"stackup_text": "", "layout_layer_z": {}}
        layout_name = layout_designs[0]
        if len(layout_designs) > 1:
            log_msg(f"找到多個 Layout 設計 {layout_designs}，使用第一個：{layout_name}")
            
        odes = oproject.SetActiveDesign(layout_name)
        oeditor = odes.SetActiveEditor("Layout")
        names = list(oeditor.GetStackupLayerNames())
        log_msg(f"從 Layout『{layout_name}』讀到 {len(names)} 個疊構層，解析中…")
        
        parsed = []
        for nm in names:
            d = parse_layer_info(oeditor.GetLayerInfo(nm))
            ltype = d.get("Type", "").lower()
            t_mil = val_to_mil(d.get("LayerThickness", "0"))
            elev = val_to_mil(d.get("LowerElevation0", "0")) or 0.0
            parsed.append((nm, ltype, t_mil if t_mil is not None else 0.0, elev))
            
        parsed.sort(key=lambda x: x[3], reverse=True)
        
        layout_layer_z = {}
        lines, cu = ["# 由 3D Layout 原生 API 讀取（厚度單位 mil）"], 0
        for nm, ltype, t_mil, elev in parsed:
            is_cu = ("signal" in ltype) or ("conductor" in ltype) or ("metal" in ltype)
            if is_cu:
                cu += 1
                lines.append(f"copper,{nm},{t_mil:.4g},{cu}")
                layout_layer_z[str(cu)] = {"lower": elev, "upper": elev + t_mil, "center": elev + t_mil / 2.0}
            else:
                lines.append(f"dielectric,{nm},{t_mil:.4g}")
                
        if cu < 2:
            log_msg("[錯誤] 辨識到的銅層少於 2 層，請確認 Layout 疊構。")
            return {"stackup_text": "", "layout_layer_z": {}}
            
        log_msg(f"已從 Layout 讀入 {cu} 層銅箔、共 {len(parsed)} 層。請接著按「依疊構自動產生」更新段數，再建立。")
        return {"stackup_text": "\n".join(lines) + "\n", "layout_layer_z": layout_layer_z}
    except Exception as e:
        log_msg(f"[錯誤] 讀取疊構失敗：{e}")
        return {"stackup_text": "", "layout_layer_z": {}}
    finally:
        try:
            if cur_design:
                oproject.SetActiveDesign(cur_design)
        except Exception:
            pass

@app.post("/api/grab")
def grab_vias(req: GrabReq):
    if not state.hfss:
        return {"status": "error", "message": "尚未連線"}
    
    try:
        if req.mode == "selected":
            try:
                names = list(state.hfss.oeditor.GetSelections())
            except Exception:
                names = list(state.hfss.modeler.oeditor.GetSelections())
            if not names:
                return {"status": "error", "message": "沒有選取物件"}
        else:
            prefix = req.prefix.strip()
            if not prefix:
                return {"status": "error", "message": "未指定前綴"}
            all_names = list(state.hfss.modeler.object_names)
            names = [n for n in all_names if n.lower().startswith(prefix.lower())]
            if not names:
                return {"status": "error", "message": f"找不到以 {prefix} 開頭的物件"}
                
        grabbed = []
        skipped = 0
        for n in names:
            if "_funnel" in n:
                skipped += 1
                continue
            bb = state.hfss.modeler[n].bounding_box
            xc = (bb[0] + bb[3]) / 2.0
            yc = (bb[1] + bb[4]) / 2.0
            z_bot, z_top = bb[2], bb[5]
            dia = max(bb[3] - bb[0], bb[4] - bb[1])
            grabbed.append({
                "name": n, "x": xc, "y": yc,
                "z_top": z_top, "z_bottom": z_bot, "dia": dia
            })
            
        msg = f"已抓取 {len(grabbed)} 個物件（含實際 Z 範圍）"
        if skipped:
            msg += f"，略過 {skipped} 個 *_funnel"
        log_msg(msg + "。")
        
        return {"status": "success", "grabbed": grabbed}
    except Exception as e:
        log_msg(f"[錯誤] 抓取失敗：{e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/build")
def build_funnels(req: BuildReq):
    if not state.hfss:
        return {"status": "error", "message": "尚未連線"}
    
    try:
        copper_top_z, copper_bot_z = parse_stackup(req.stackup)
        changes = parse_changes(req.changes)
        
        gdrill = req.drill
        gfinish = req.finish
        base_changes = resolve_changes(changes, gdrill, gfinish)
        base_segs = get_segments(copper_top_z, copper_bot_z, base_changes)
        
        log_msg(f"疊構解析完成：銅層 {sorted(copper_top_z.keys())}；段數 {len(changes)}；寬端 {gdrill:g} / 窄端 {gfinish:g} mil。")
        
        jobs = []
        if req.src_mode == "grab":
            if not req.grabbed:
                return {"status": "error", "message": "尚未抓取"}
            
            replace = req.replace
            fit = req.fit
            autodia = req.autodia
            ratio = (gfinish / gdrill) if gdrill else 1.0
            use_realz = fit and bool(req.layout_layer_z)
            
            if use_realz:
                log_msg("採用『layout 真實層 Z』定位節點（offset 對齊、不拉伸）。")
                
            for g in req.grabbed:
                if autodia and g.get("dia"):
                    via_changes = resolve_changes(changes, g["dia"], g["dia"] * ratio)
                else:
                    via_changes = base_changes
                    
                res = get_segments_realz(req.layout_layer_z, via_changes, g["z_top"], g["z_bottom"]) if use_realz else None
                if res is not None:
                    segs, offset, residual = res
                    note = "" if abs(residual) < 0.5 else "（殘差較大，via 可能含 stub/防焊，節點仍以真實層為準）"
                    log_msg(f"  {g['name']}：offset={offset:+.3f} mil、端點殘差={residual:+.3f} mil{note}")
                elif fit:
                    segs = get_segments_fit(copper_top_z, copper_bot_z, via_changes, g["z_top"], g["z_bottom"])
                else:
                    segs = get_segments(copper_top_z, copper_bot_z, via_changes)
                    
                jobs.append((g["x"], g["y"], segs, g["name"] + "_funnel", g["name"] if replace else None))
        else:
            coords = parse_coords(req.coords)
            for idx, (x, y) in enumerate(coords):
                jobs.append((x, y, base_segs, f"via_{idx}", None))
                
        if not jobs:
            return {"status": "error", "message": "沒有座標"}
            
        count = 0
        for x, y, segs, prefix, to_delete in jobs:
            if to_delete:
                state.hfss.modeler[to_delete].delete()
                log_msg(f"已刪除原圓柱：{to_delete}")
            
            parts = []
            for i, seg in enumerate(segs):
                kwargs = dict(origin=[x, y, seg["z_bottom"]],
                              bottom_radius=seg["r_bottom"],
                              top_radius=seg["r_top"],
                              height=seg["height"],
                              name=f"{prefix}_{i}",
                              material=req.material)
                try:
                    cone = state.hfss.modeler.create_cone(orientation="Z", **kwargs)
                except TypeError:
                    cone = state.hfss.modeler.create_cone(cs_axis="Z", **kwargs)
                parts.append(cone.name)
            if len(parts) > 1:
                state.hfss.modeler.unite(parts)
            
            count += 1
            z0, z1 = segs[-1]["z_bottom"], segs[0]["z_bottom"] + segs[0]["height"]
            log_msg(f"已建立漏斗 via：{parts[0]} @ ({x:.3f}, {y:.3f}) Z:[{z0:.3f}, {z1:.3f}]")
            
        log_msg(f"完成！共建立 {count} 顆漏斗 via。")
        return {"status": "success", "count": count}
    except Exception as e:
        err = f"[錯誤] 建立失敗：{e}\n{traceback.format_exc()}"
        log_msg(err)
        return {"status": "error", "message": str(e)}
