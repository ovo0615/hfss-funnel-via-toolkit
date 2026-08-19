# -*- coding: utf-8 -*-
# =====================================================================
#  HFSS 3D 漏斗狀（堆疊雷射微孔 / stacked laser via）建模工具  ── GUI 版
# ---------------------------------------------------------------------
#  用途：
#    HFSS 3D Layout 只能建「等徑圓柱 via」，無法做漏斗狀 taper。
#    本工具在 HFSS 3D 模型器中，以「多段圓錐台（cone frustum）」沿 Z 軸
#    堆疊，組出上寬下窄的漏斗狀 via，所有參數皆可於 GUI 直接修改。
#
#  需先安裝的套件 / 環境：
#    1. Ansys Electronics Desktop（含 HFSS）── 已安裝的正式版本（預設 2026 R1）
#    2. PyAEDT：  pip install pyaedt        （提供 ansys.aedt.core）
#    3. Tkinter ── Python 內建，無需另外安裝
#
#  座標約定：
#    Z = 0 在最上方（top solder mask 上表面），往下為負。
#    每段圓錐台：下底＝窄端（Finish）、上底＝寬端（Drill），形成漏斗。
# =====================================================================

import tkinter as tk
from tkinter import ttk, messagebox

# 字型（依個人規則：中文微軟正黑體、英數 Calibri）
FONT_UI   = ("Microsoft JhengHei", 9)     # 介面文字（含中文）
FONT_CODE = ("Calibri", 10)               # 數值 / 表格輸入（英數為主）

# 預設疊構（取自 Original Design，單位 mil；請依實際疊構核對）
DEFAULT_STACKUP = """\
# 格式：kind,name,thickness[,layer]
# kind = soldermask / copper / dielectric ；copper 需填 layer 編號
soldermask,SM_top,0.80
copper,L1,1.20,1
dielectric,pp,2.30
copper,L2,1.20,2
dielectric,pp,3.30
copper,L3,1.00,3
dielectric,pp,3.30
copper,L4,1.20,4
dielectric,pp,3.30
copper,L5,1.20,5
dielectric,CORE,4.00
copper,L6,1.20,6
dielectric,pp,3.30
copper,L7,1.20,7
dielectric,pp,3.30
copper,L8,1.20,8
dielectric,pp,3.30
copper,L9,1.00,9
dielectric,pp,2.30
copper,L10,0.80,10
soldermask,SM_bot,0.80
"""

# 預設 layer change 表（取自你提供的資料）
# 寬度（直徑）統一在右側「Via 寬度」面板設定；此處只需填層別轉換。
DEFAULT_CHANGES = """\
# 格式：start,end          （寬度用右側面板）
# 進階：start,end,drill,finish  ← 想個別覆寫寬度時才加後兩欄
1,2
2,3
3,4
4,5
5,6
"""

DEFAULT_COORDS = """\
# 格式：x,y  （mil），每行一顆 via
0,0
"""


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
        kind, name, thickness = parts[0], parts[1], float(parts[2])
        z_top, z_bot = z, z - thickness
        if kind == "copper":
            layer = int(parts[3])
            copper_top_z[layer] = z_top
            copper_bot_z[layer] = z_bot
        z = z_bot
    return copper_top_z, copper_bot_z


def parse_changes(text):
    """回傳 [(start, end, drill_or_None, finish_or_None), ...]。
    僅 2 欄時寬度回傳 None（之後由全域寬度面板填入）；4 欄時為個別覆寫。"""
    changes = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        p = [x.strip() for x in line.split(",")]
        if len(p) >= 4:
            changes.append((int(p[0]), int(p[1]), float(p[2]), float(p[3])))
        else:
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
        coords.append((float(p[0]), float(p[1])))
    return coords


# =====================================================================
#  GUI
# =====================================================================
class FunnelViaGUI:
    def __init__(self, root):
        self.root = root
        self.hfss = None              # PyAEDT Hfss 物件
        self.grabbed = []             # 抓取到的 via： [(name, x, y), ...]
        self.layout_layer_z = {}      # 從 layout 讀到的真實層 Z：{layer: {upper,lower,center}}（mil）

        root.title("HFSS 漏斗 Via 建模工具 — 虎門科技 Jeff Hong")
        root.geometry("980x720")
        root.option_add("*Font", FONT_UI)

        self._build_widgets()

    # ---------- 介面 ----------
    def _build_widgets(self):
        # 連線列
        top = ttk.LabelFrame(self.root, text="連線設定")
        top.pack(fill="x", padx=8, pady=6)
        ttk.Label(top, text="AEDT 版本：").grid(row=0, column=0, padx=4, pady=6, sticky="w")
        self.ver_var = tk.StringVar(value="2026.1")          # 預設 2026 R1
        ttk.Entry(top, textvariable=self.ver_var, width=12, font=FONT_CODE)\
            .grid(row=0, column=1, padx=4)
        ttk.Label(top, text="（2026 R1 = 2026.1）").grid(row=0, column=2, padx=4, sticky="w")
        ttk.Label(top, text="via 材質：").grid(row=0, column=3, padx=4, sticky="w")
        self.mat_var = tk.StringVar(value="copper")
        ttk.Entry(top, textvariable=self.mat_var, width=12, font=FONT_CODE)\
            .grid(row=0, column=4, padx=4)
        self.btn_connect = ttk.Button(top, text="連線 AEDT", command=self.on_connect)
        self.btn_connect.grid(row=0, column=5, padx=8)
        self.status_var = tk.StringVar(value="尚未連線")
        ttk.Label(top, textvariable=self.status_var, foreground="#888")\
            .grid(row=0, column=6, padx=6)

        # 中段：疊構 + layer change
        mid = ttk.Frame(self.root)
        mid.pack(fill="both", expand=False, padx=8, pady=2)

        sf = ttk.LabelFrame(mid, text="疊構表 STACKUP（可直接編輯）")
        sf.pack(side="left", fill="both", expand=True, padx=(0, 4))
        self.txt_stackup = tk.Text(sf, width=44, height=16, font=FONT_CODE, wrap="none")
        self.txt_stackup.pack(fill="both", expand=True, padx=4, pady=4)
        self.txt_stackup.insert("1.0", DEFAULT_STACKUP)
        # 用 AEDT 原生 API 從同專案 3D Layout 設計讀真實疊構（取代手打，不依賴 pyedb）
        ttk.Button(sf, text="⤵ 從 3D Layout 設計讀取真實疊構",
                   command=self.on_read_stackup_from_edb)\
            .pack(side="bottom", fill="x", padx=4, pady=(0, 4))

        cf = ttk.LabelFrame(mid, text="Layer change 表（只填 start,end）")
        cf.pack(side="left", fill="both", expand=True, padx=4)
        self.txt_changes = tk.Text(cf, width=24, height=16, font=FONT_CODE, wrap="none")
        self.txt_changes.pack(fill="both", expand=True, padx=4, pady=4)
        self.txt_changes.insert("1.0", DEFAULT_CHANGES)
        # 改動 layer change 行數時，預覽圖跟著更新段數
        self.txt_changes.bind("<KeyRelease>", lambda e: self._draw_preview())
        # 功能①：依疊構自動產生 Layer change（每相鄰銅層一段）
        ttk.Button(cf, text="↻ 依疊構自動產生（每相鄰銅層一段）",
                   command=self.on_autogen_changes)\
            .pack(side="bottom", fill="x", padx=4, pady=(0, 4))

        # Via 寬度面板 + 即時預覽
        wf = ttk.LabelFrame(mid, text="Via 寬度（直徑，mil）")
        wf.pack(side="left", fill="both", expand=False, padx=(4, 0))

        self.drill_var  = tk.StringVar(value="4.9")   # 寬端（上）
        self.finish_var = tk.StringVar(value="4.0")   # 窄端（下）
        ttk.Label(wf, text="寬端（上, Drill）：").grid(row=0, column=0, sticky="e", padx=4, pady=6)
        e1 = ttk.Entry(wf, textvariable=self.drill_var, width=8, font=FONT_CODE)
        e1.grid(row=0, column=1, padx=4)
        ttk.Label(wf, text="窄端（下, Finish）：").grid(row=1, column=0, sticky="e", padx=4, pady=6)
        e2 = ttk.Entry(wf, textvariable=self.finish_var, width=8, font=FONT_CODE)
        e2.grid(row=1, column=1, padx=4)
        # 數字一改就重畫預覽
        self.drill_var.trace_add("write", lambda *a: self._draw_preview())
        self.finish_var.trace_add("write", lambda *a: self._draw_preview())

        self.autodia_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(wf, text="寬端＝原選取 via 外徑（自動帶入）",
                        variable=self.autodia_var, command=self._apply_autodia)\
            .grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=2)

        ttk.Label(wf, text="側視預覽：").grid(row=3, column=0, columnspan=2, sticky="w", padx=4)
        self.preview = tk.Canvas(wf, width=150, height=240, background="#ffffff",
                                 highlightthickness=1, highlightbackground="#ccc")
        self.preview.grid(row=4, column=0, columnspan=2, padx=4, pady=4)

        # 下段：Via 來源
        src = ttk.LabelFrame(self.root, text="Via 來源")
        src.pack(fill="x", padx=8, pady=6)
        self.src_var = tk.StringVar(value="grab")
        ttk.Radiobutton(src, text="抓取 AEDT 中『選取的 Via』", value="grab",
                        variable=self.src_var, command=self._refresh_src)\
            .grid(row=0, column=0, padx=6, pady=4, sticky="w")
        ttk.Radiobutton(src, text="手動輸入座標", value="manual",
                        variable=self.src_var, command=self._refresh_src)\
            .grid(row=0, column=1, padx=6, pady=4, sticky="w")

        # 抓取模式區
        self.grab_frame = ttk.Frame(src)
        self.grab_frame.grid(row=1, column=0, columnspan=3, sticky="we", padx=6)

        # 第一列：兩種抓取方式
        ttk.Button(self.grab_frame, text="① 抓取 AEDT 中『選取的 via』",
                   command=self.on_grab).grid(row=0, column=0, padx=4, pady=4, sticky="w")
        self.fit_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.grab_frame,
                        text="依 via 頭尾錨定＋疊構比例定位節點（建議：填滿且節點落在真實層）",
                        variable=self.fit_var).grid(row=0, column=1, columnspan=3,
                                                    padx=10, sticky="w")

        # 第二列：自動抓取所有名稱符合前綴的物件
        ttk.Button(self.grab_frame, text="①′ 自動抓取所有名稱開頭符合的物件",
                   command=self.on_grab_all).grid(row=1, column=0, padx=4, pady=4, sticky="w")
        ttk.Label(self.grab_frame, text="名稱開頭：").grid(row=1, column=1, sticky="e")
        self.prefix_var = tk.StringVar(value="via")
        ttk.Entry(self.grab_frame, textvariable=self.prefix_var, width=10, font=FONT_CODE)\
            .grid(row=1, column=2, sticky="w")
        ttk.Label(self.grab_frame, text="（不分大小寫，自動略過 *_funnel）",
                  foreground="#888").grid(row=1, column=3, sticky="w", padx=4)

        # 第三列：取代模式
        self.replace_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.grab_frame, text="取代模式：建立後刪除原本的圓柱 via",
                        variable=self.replace_var).grid(row=2, column=0, columnspan=4,
                                                        padx=4, sticky="w")
        self.lst_grab = tk.Listbox(self.grab_frame, height=5, font=FONT_CODE)
        self.lst_grab.grid(row=3, column=0, columnspan=4, sticky="we", padx=4, pady=4)
        self.grab_frame.columnconfigure(3, weight=1)

        # 手動座標區
        self.manual_frame = ttk.Frame(src)
        self.txt_coords = tk.Text(self.manual_frame, width=40, height=5,
                                  font=FONT_CODE, wrap="none")
        self.txt_coords.pack(fill="x", padx=4, pady=4)
        self.txt_coords.insert("1.0", DEFAULT_COORDS)

        # 執行
        run = ttk.Frame(self.root)
        run.pack(fill="x", padx=8, pady=4)
        self.btn_build = ttk.Button(run, text="② 建立漏斗 Via", command=self.on_build)
        self.btn_build.pack(side="left", padx=4)

        # Log
        lf = ttk.LabelFrame(self.root, text="執行訊息")
        lf.pack(fill="both", expand=True, padx=8, pady=6)
        self.txt_log = tk.Text(lf, height=8, font=FONT_CODE, state="disabled",
                               background="#1e1e1e", foreground="#d4d4d4")
        self.txt_log.pack(fill="both", expand=True, padx=4, pady=4)

        self._refresh_src()
        self._draw_preview()

    def _refresh_src(self):
        if self.src_var.get() == "grab":
            self.manual_frame.grid_forget()
            self.grab_frame.grid(row=1, column=0, columnspan=3, sticky="we", padx=6)
        else:
            self.grab_frame.grid_forget()
            self.manual_frame.grid(row=1, column=0, columnspan=3, sticky="we", padx=6)

    def _apply_autodia(self):
        """勾選『寬端＝原 via 外徑』時，立即把抓到的 via 外徑帶入寬端欄位並更新預覽。"""
        if not self.autodia_var.get():
            return
        if not self.grabbed:
            self.log("已勾選『寬端＝原 via 外徑』；請先抓取 via，數值會自動帶入。")
            return
        dias = [g["dia"] for g in self.grabbed if g.get("dia")]
        if not dias:
            return
        d0 = dias[0]
        if max(dias) - min(dias) > 1e-3:
            self.log(f"[提醒] 選取 via 外徑不一致（{min(dias):.3f}~{max(dias):.3f}）；"
                     f"預覽以第一顆 {d0:.3f} 為準，建立時各 via 仍用各自外徑。")
        self.drill_var.set(f"{d0:.4g}")     # 觸發 trace → 預覽自動更新

    def _draw_preview(self):
        """依寬端/窄端直徑與段數，畫出漏斗側視剖面（堆疊梯形）。"""
        c = self.preview
        c.delete("all")
        W = int(c["width"]); H = int(c["height"])
        # 讀寬度
        try:
            drill = float(self.drill_var.get())
            finish = float(self.finish_var.get())
        except ValueError:
            c.create_text(W // 2, H // 2, text="寬度數值無效", fill="#c00")
            return
        if drill <= 0 or finish <= 0:
            c.create_text(W // 2, H // 2, text="寬度需 > 0", fill="#c00")
            return
        # 讀段數
        try:
            n = max(1, len(parse_changes(self.txt_changes.get("1.0", "end"))))
        except Exception:
            n = 1

        pad_x, pad_top, pad_bot = 18, 16, 22
        plot_h = H - pad_top - pad_bot
        seg_h = plot_h / n
        cx = W / 2
        scale = (W - 2 * pad_x) / drill        # 以寬端對應可用寬度
        half_d = drill * scale / 2
        half_f = finish * scale / 2

        for i in range(n):
            y_top = pad_top + i * seg_h
            y_bot = y_top + seg_h
            # 每段：上寬（drill）下窄（finish）的梯形 → 堆疊成聖誕樹狀漏斗
            c.create_polygon(cx - half_d, y_top, cx + half_d, y_top,
                             cx + half_f, y_bot, cx - half_f, y_bot,
                             fill="#e8a06a", outline="#b5651d")
        # 中心線
        c.create_line(cx, pad_top, cx, H - pad_bot, fill="#bbb", dash=(2, 2))
        # 標註
        c.create_text(cx, 8, text=f"上 {drill:g}", fill="#333", font=("Calibri", 8))
        c.create_text(cx, H - 10, text=f"下 {finish:g}", fill="#333", font=("Calibri", 8))

    # ---------- 工具 ----------
    def log(self, msg):
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", msg + "\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")
        self.root.update_idletasks()

    def _busy(self, busy):
        state = "disabled" if busy else "normal"
        for b in (self.btn_connect, self.btn_build):
            b.configure(state=state)
        self.root.update_idletasks()

    # ---------- 事件：連線 ----------
    def on_connect(self):
        self._busy(True)
        try:
            self.log(f"連線 AEDT {self.ver_var.get()} 中…")
            from ansys.aedt.core import Hfss
            self.hfss = Hfss(version=self.ver_var.get(), new_desktop=False)
            self.hfss.modeler.model_units = "mil"
            self.status_var.set(f"已連線：{self.hfss.design_name}")
            self.log(f"連線成功，目前設計：{self.hfss.design_name}（單位 mil）")
        except Exception as e:
            self.status_var.set("連線失敗")
            self.log(f"[錯誤] 連線失敗：{e}")
            messagebox.showerror("連線失敗", str(e))
        finally:
            self._busy(False)

    # ---------- 共用：把一批物件名稱讀成 grabbed 清單 ----------
    def _populate_grabbed(self, names):
        self.grabbed = []
        self.lst_grab.delete(0, "end")
        skipped = 0
        for n in names:
            if "_funnel" in n:                  # 略過本工具先前產生的漏斗
                skipped += 1
                continue
            bb = self.hfss.modeler[n].bounding_box   # [xmin,ymin,zmin,xmax,ymax,zmax]
            xc = (bb[0] + bb[3]) / 2.0
            yc = (bb[1] + bb[4]) / 2.0
            z_bot, z_top = bb[2], bb[5]              # via 實際的 Z 下界 / 上界
            dia = max(bb[3] - bb[0], bb[4] - bb[1])  # via 外徑（取 XY 較大邊）
            self.grabbed.append({"name": n, "x": xc, "y": yc,
                                 "z_top": z_top, "z_bottom": z_bot, "dia": dia})
            self.lst_grab.insert(
                "end",
                f"{n}  →  ({xc:.3f}, {yc:.3f})  Z:[{z_bot:.3f}, {z_top:.3f}]  ⌀{dia:.2f}")
        msg = f"已抓取 {len(self.grabbed)} 個物件（含實際 Z 範圍）"
        if skipped:
            msg += f"，略過 {skipped} 個 *_funnel"
        self.log(msg + "。")
        self._apply_autodia()      # 若已勾自動帶入，抓取後立即更新寬端與預覽

    # ---------- 事件：抓取『選取的』via ----------
    def on_grab(self):
        if not self.hfss:
            messagebox.showwarning("尚未連線", "請先按「連線 AEDT」。")
            return
        try:
            try:
                names = list(self.hfss.oeditor.GetSelections())
            except Exception:
                names = list(self.hfss.modeler.oeditor.GetSelections())
            if not names:
                messagebox.showinfo("沒有選取物件",
                                    "請先在 AEDT 模型器中點選 / 框選要轉換的 via。")
                return
            self._populate_grabbed(names)
        except Exception as e:
            self.log(f"[錯誤] 抓取失敗：{e}")
            messagebox.showerror("抓取失敗", str(e))

    # ---------- 事件：自動抓取『所有名稱開頭符合』的物件 ----------
    def on_grab_all(self):
        if not self.hfss:
            messagebox.showwarning("尚未連線", "請先按「連線 AEDT」。")
            return
        prefix = self.prefix_var.get().strip()
        if not prefix:
            messagebox.showinfo("未指定前綴", "請先在「名稱開頭」輸入要比對的前綴，例如 via。")
            return
        try:
            all_names = list(self.hfss.modeler.object_names)   # 設計中所有 3D 物件
            names = [n for n in all_names if n.lower().startswith(prefix.lower())]
            if not names:
                messagebox.showinfo("找不到物件",
                                    f"設計中沒有名稱以「{prefix}」開頭的物件。")
                return
            self.log(f"以前綴「{prefix}」比對到 {len(names)} 個物件，讀取中…")
            self._populate_grabbed(names)
        except Exception as e:
            self.log(f"[錯誤] 自動抓取失敗：{e}")
            messagebox.showerror("自動抓取失敗", str(e))

    # ---------- 核心：建立漏斗 ----------
    def _build_one(self, x, y, segments, name_prefix):
        parts = []
        for i, seg in enumerate(segments):
            kwargs = dict(origin=[x, y, seg["z_bottom"]],
                          bottom_radius=seg["r_bottom"],
                          top_radius=seg["r_top"],
                          height=seg["height"],
                          name=f"{name_prefix}_{i}",
                          material=self.mat_var.get())
            try:
                cone = self.hfss.modeler.create_cone(orientation="Z", **kwargs)
            except TypeError:
                # 少數版本參數名為 cs_axis
                cone = self.hfss.modeler.create_cone(cs_axis="Z", **kwargs)
            parts.append(cone.name)
        if len(parts) > 1:
            self.hfss.modeler.unite(parts)
        return parts[0]

    @staticmethod
    def _resolve_changes(changes, drill, finish):
        """把 layer change 表中未指定寬度（None）的列，用全域 drill/finish 補上。"""
        out = []
        for s, e, d, f in changes:
            out.append((s, e,
                        d if d is not None else drill,
                        f if f is not None else finish))
        return out

    def _segments(self, copper_top_z, copper_bot_z, changes):
        """用疊構表算出的『絕對 Z』分段（手動座標模式使用）。"""
        segs = []
        for start, end, drill_d, finish_d in changes:
            z_top = copper_bot_z[start]    # 上層底面（寬端 / Drill）
            z_bot = copper_top_z[end]      # 下層頂面（窄端 / Finish）
            segs.append({"z_bottom": z_bot,
                         "height": z_top - z_bot,
                         "r_bottom": finish_d / 2.0,
                         "r_top": drill_d / 2.0})
        return segs

    def _segments_fit(self, copper_top_z, copper_bot_z, changes,
                      z_top_via, z_bottom_via):
        """以 via 頭尾兩端為錨點，依疊構各銅層的『相對比例』定位每個節點。

        作法：取 change 表涉及的層序 [L0..Ln]，用各層在疊構中的中心 Z 當比例，
        將最上層映射到 via 頂、最下層映射到 via 底，中間層線性內插。
        → 漏斗一定填滿整根 via，且每個節點落在與疊構比例一致的真實層位置
          （每一節介於相鄰兩層／兩個 non-functional pad 之間）。
        對疊構『整體縮放誤差』免疫，只要各層『相對比例』正確即可。"""
        layers = [changes[0][0]] + [c[1] for c in changes]      # 例 [1,2,...,10]
        cz = {L: (copper_top_z[L] + copper_bot_z[L]) / 2.0 for L in layers}
        s_top, s_bot = cz[layers[0]], cz[layers[-1]]            # 疊構座標的頭/尾
        span_s = s_top - s_bot
        span_m = z_top_via - z_bottom_via                      # 模型 via 實際跨距

        def mapz(z):                                            # 疊構 Z → 模型 Z
            if abs(span_s) < 1e-12:
                return z_top_via
            return z_bottom_via + (z - s_bot) / span_s * span_m

        out = []
        for start, end, drill_d, finish_d in changes:
            zt, zb = mapz(cz[start]), mapz(cz[end])            # 上層→寬端、下層→窄端
            out.append({"z_bottom": zb, "height": zt - zb,
                        "r_bottom": finish_d / 2.0,
                        "r_top": drill_d / 2.0})
        return out

    def _segments_realz(self, changes, z_top_via, z_bottom_via):
        """最精準：節點直接放在『layout 讀到的真實層 Z』，只用 via 做整體 offset 對齊
        （純平移、不拉伸），因此每段交界落在真實銅層（pad）上。
        offset 取兩端誤差平均；端點殘差大代表 via 含 stub/防焊（會記錄提醒）。
        回傳 (segments, offset, residual)；缺真實 Z 時回傳 None 由上層改用 fit。"""
        ll = self.layout_layer_z
        layers = [changes[0][0]] + [c[1] for c in changes]
        if not ll or not all(L in ll for L in layers):
            return None
        real_top = ll[layers[0]]["upper"]      # 最上層銅箔上表面
        real_bot = ll[layers[-1]]["lower"]     # 最下層銅箔下表面
        off_top = z_top_via - real_top
        off_bot = z_bottom_via - real_bot
        offset = (off_top + off_bot) / 2.0
        residual = off_top - off_bot
        out = []
        for start, end, drill_d, finish_d in changes:
            zt = ll[start]["center"] + offset
            zb = ll[end]["center"] + offset
            out.append({"z_bottom": zb, "height": zt - zb,
                        "r_bottom": finish_d / 2.0,
                        "r_top": drill_d / 2.0})
        return out, offset, residual

    def on_autogen_changes(self):
        """功能①：依疊構自動產生 Layer change（每相鄰銅層一段）。"""
        try:
            copper_top_z, _ = parse_stackup(self.txt_stackup.get("1.0", "end"))
            layers = sorted(copper_top_z.keys())
            if len(layers) < 2:
                messagebox.showinfo("銅層不足",
                                    "疊構表中可辨識的銅層少於 2 層，無法產生。")
                return
            lines = ["# 由疊構自動產生（每相鄰銅層一段）"]
            for a, b in zip(layers, layers[1:]):
                lines.append(f"{a},{b}")
            self.txt_changes.delete("1.0", "end")
            self.txt_changes.insert("1.0", "\n".join(lines) + "\n")
            self._draw_preview()
            self.log(f"已依疊構產生 {len(layers) - 1} 段 Layer change"
                     f"（銅層 {layers[0]}→{layers[-1]}）。")
        except Exception as e:
            self.log(f"[錯誤] 自動產生失敗：{e}")
            messagebox.showerror("自動產生失敗", str(e))

    # 厚度單位 → mil 換算（AEDT GetLayerInfo 多為 meter）
    _UNIT2MIL = {"meter": 39370.0787, "m": 39370.0787, "cm": 393.700787,
                 "mm": 39.3700787, "um": 0.0393700787, "micron": 0.0393700787,
                 "nm": 3.93700787e-5, "mil": 1.0, "in": 1000.0, "inch": 1000.0}

    @staticmethod
    def _val_to_mil(s):
        """把 '0.0001meter' / '5mil' / '0.12mm' 這類字串換算成 mil。"""
        import re
        m = re.match(r"\s*([-+0-9.eE]+)\s*([a-zA-Z]*)", str(s))
        if not m:
            return None
        val = float(m.group(1))
        unit = (m.group(2) or "meter").lower()
        return val * FunnelViaGUI._UNIT2MIL.get(unit, 39370.0787)

    @staticmethod
    def _parse_layer_info(infos):
        """GetLayerInfo 回傳 ['Key: Value', ...] → dict。"""
        d = {}
        for it in infos:
            if ": " in it:
                k, v = it.split(": ", 1)
                d[k.strip()] = v.strip()
        return d

    def on_read_stackup_from_edb(self):
        """用 AEDT 原生 API 從同專案的 3D Layout 設計讀真實疊構（不依賴 pyedb）。
        模型由 3D Layout 轉成 3D 時，3D 模型的 Z 即照 layout 層 elevation 擺放，
        讀回真實層數與厚度後，fit 的節點就會精準落在每層銅箔上。"""
        if not self.hfss:
            messagebox.showwarning("尚未連線", "請先按「連線 AEDT」。")
            return
        self._busy(True)
        cur_design = getattr(self.hfss, "design_name", None)
        oproject = self.hfss.oproject
        try:
            # 1) 在專案中找出 3D Layout 設計
            try:
                design_names = list(self.hfss.design_list)
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
                msg = "專案中找不到 3D Layout 設計，無法讀取疊構。"
                self.log("[錯誤] " + msg); messagebox.showerror("找不到 Layout", msg)
                return
            layout_name = layout_designs[0]
            if len(layout_designs) > 1:
                self.log(f"找到多個 Layout 設計 {layout_designs}，使用第一個：{layout_name}")

            # 2) 取得 Layout 編輯器並讀疊構層
            odes = oproject.SetActiveDesign(layout_name)
            oeditor = odes.SetActiveEditor("Layout")
            names = list(oeditor.GetStackupLayerNames())
            self.log(f"從 Layout『{layout_name}』讀到 {len(names)} 個疊構層，解析中…")

            parsed = []
            for nm in names:
                d = self._parse_layer_info(oeditor.GetLayerInfo(nm))
                ltype = d.get("Type", "").lower()
                t_mil = self._val_to_mil(d.get("LayerThickness", "0"))
                elev = self._val_to_mil(d.get("LowerElevation0", "0")) or 0.0
                parsed.append((nm, ltype, t_mil if t_mil is not None else 0.0, elev))

            # 由上往下（lower_elevation 大的在上）
            parsed.sort(key=lambda x: x[3], reverse=True)

            self.layout_layer_z = {}        # 重置真實層 Z
            lines, cu = ["# 由 3D Layout 原生 API 讀取（厚度單位 mil）"], 0
            for nm, ltype, t_mil, elev in parsed:
                is_cu = ("signal" in ltype) or ("conductor" in ltype) or ("metal" in ltype)
                if is_cu:
                    cu += 1
                    lines.append(f"copper,{nm},{t_mil:.4g},{cu}")
                    # 記錄該銅層的真實 Z（elev 為下表面，往上加厚度）
                    self.layout_layer_z[cu] = {"lower": elev, "upper": elev + t_mil,
                                               "center": elev + t_mil / 2.0}
                else:
                    lines.append(f"dielectric,{nm},{t_mil:.4g}")

            if cu < 2:
                self.log("[錯誤] 辨識到的銅層少於 2 層，請確認 Layout 疊構。")
                return
            self.txt_stackup.delete("1.0", "end")
            self.txt_stackup.insert("1.0", "\n".join(lines) + "\n")
            self._draw_preview()
            self.log(f"已從 Layout 讀入 {cu} 層銅箔、共 {len(parsed)} 層。"
                     f"請接著按「↻ 依疊構自動產生」更新段數，再建立。")
        except Exception as e:
            self.log(f"[錯誤] 讀取疊構失敗：{e}")
            messagebox.showerror("讀取疊構失敗", str(e))
        finally:
            # 還原使用者原本的作用中設計
            try:
                if cur_design:
                    oproject.SetActiveDesign(cur_design)
            except Exception:
                pass
            self._busy(False)

    def on_build(self):
        if not self.hfss:
            messagebox.showwarning("尚未連線", "請先按「連線 AEDT」。")
            return
        self._busy(True)
        try:
            copper_top_z, copper_bot_z = parse_stackup(self.txt_stackup.get("1.0", "end"))
            changes = parse_changes(self.txt_changes.get("1.0", "end"))
            # 全域寬度（直徑）來自右側「Via 寬度」面板
            gdrill = float(self.drill_var.get())
            gfinish = float(self.finish_var.get())
            base_changes = self._resolve_changes(changes, gdrill, gfinish)
            base_segs = self._segments(copper_top_z, copper_bot_z, base_changes)
            self.log(f"疊構解析完成：銅層 {sorted(copper_top_z)}；"
                     f"段數 {len(changes)}；寬端 {gdrill:g} / 窄端 {gfinish:g} mil。")

            # 決定每個 job：(x, y, segments, prefix, name_to_delete or None)
            jobs = []
            if self.src_var.get() == "grab":
                if not self.grabbed:
                    messagebox.showinfo("尚未抓取", "請先按「抓取」取得選取的 via。")
                    return
                replace = self.replace_var.get()
                fit = self.fit_var.get()
                autodia = self.autodia_var.get()
                ratio = (gfinish / gdrill) if gdrill else 1.0
                use_realz = fit and bool(self.layout_layer_z)
                if use_realz:
                    self.log("採用『layout 真實層 Z』定位節點（offset 對齊、不拉伸）。")
                for g in self.grabbed:
                    if autodia and g.get("dia"):
                        # 寬端＝原 via 外徑；窄端依相同錐度比例縮放
                        via_changes = self._resolve_changes(
                            changes, g["dia"], g["dia"] * ratio)
                    else:
                        via_changes = base_changes
                    res = self._segments_realz(via_changes, g["z_top"], g["z_bottom"]) \
                        if use_realz else None
                    if res is not None:
                        segs, offset, residual = res
                        note = "" if abs(residual) < 0.5 else \
                            "（殘差較大，via 可能含 stub/防焊，節點仍以真實層為準）"
                        self.log(f"  {g['name']}：offset={offset:+.3f} mil、"
                                 f"端點殘差={residual:+.3f} mil{note}")
                    elif fit:
                        # 後備：以 via 頭尾為錨點、依疊構比例定位節點
                        segs = self._segments_fit(copper_top_z, copper_bot_z,
                                                  via_changes, g["z_top"], g["z_bottom"])
                    else:
                        segs = self._segments(copper_top_z, copper_bot_z, via_changes)
                    jobs.append((g["x"], g["y"], segs, g["name"] + "_funnel",
                                 g["name"] if replace else None))
            else:
                coords = parse_coords(self.txt_coords.get("1.0", "end"))
                for idx, (x, y) in enumerate(coords):
                    jobs.append((x, y, base_segs, f"via_{idx}", None))

            if not jobs:
                messagebox.showinfo("沒有座標", "找不到任何 via 座標。")
                return

            count = 0
            for x, y, segs, prefix, to_delete in jobs:
                if to_delete:
                    self.hfss.modeler[to_delete].delete()
                    self.log(f"已刪除原圓柱：{to_delete}")
                name = self._build_one(x, y, segs, prefix)
                count += 1
                z0, z1 = segs[-1]["z_bottom"], segs[0]["z_bottom"] + segs[0]["height"]
                self.log(f"已建立漏斗 via：{name} @ ({x:.3f}, {y:.3f})  "
                         f"Z:[{z0:.3f}, {z1:.3f}]")

            self.log(f"完成！共建立 {count} 顆漏斗 via。")
            messagebox.showinfo("完成", f"共建立 {count} 顆漏斗 via。")
        except Exception as e:
            self.log(f"[錯誤] 建立失敗：{e}")
            messagebox.showerror("建立失敗", str(e))
        finally:
            self._busy(False)


if __name__ == "__main__":
    root = tk.Tk()
    app = FunnelViaGUI(root)
    root.mainloop()
