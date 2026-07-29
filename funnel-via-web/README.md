# HFSS 3D 漏斗狀 Via 網頁版建模工具（Web App）

此工具由虎門科技資深技術工程師 Jeff Hong 洪敬傑提供。

## 簡介

將原本基於 Tkinter 的 `funnel_via_gui.py` 轉換為網頁應用程式。前端使用 React + Vite 搭配 Three.js 提供即時 3D 幾何預覽，後端使用 FastAPI 與 PyAEDT 負責實際的模型控制與生成。

production 模式下前端已預先建置於 `frontend/dist`，由 FastAPI 以**單一 localhost 埠**一併服務，**一般使用者不需要安裝 Node.js**。

```text
start.bat → start.ps1 → backend\.venv\Scripts\python.exe → uvicorn → http://127.0.0.1:8010
```

## 一般使用者

1. 開啟 AEDT，載入要加 via 的 HFSS 專案與設計。
2. **雙擊 `start.bat`**。
3. 首次啟動會自動偵測相容 Python、建立 `backend\.venv` 並下載套件（需要網路，約數分鐘）。
4. 服務就緒後自動開啟瀏覽器 `http://127.0.0.1:8010`。
5. **關閉啟動視窗即停止服務。**

其他用法：

```bat
start.bat -Port 8020
```

```bat
start.bat -CheckOnly
```

- `-Port`：8010 被佔用時改用其他埠。
- `-CheckOnly`：只做環境檢查與套件安裝，不啟動服務、不佔用連接埠。

完整操作說明：[../docs/操作說明.md](../docs/操作說明.md)

## 環境需求

| 項目 | 說明 |
|------|------|
| Windows 10／11（64 位元） | 執行環境 |
| Ansys Electronics Desktop（含 HFSS） | **商業授權**，需自行安裝。本工具是遙控您已安裝的 AEDT |
| Python 3.10／3.11／3.12（64 位元） | 啟動腳本自動尋找；若只有不相容版本，會以 WinGet 於使用者範圍額外安裝 3.12，不會動到既有 Python |
| Node.js 18+ | **僅維護者開發模式需要**，一般使用者不需要 |

後端套件（`backend/requirements.lock.txt`，只裝在 `backend/.venv` 內）：

| 套件 | 版本 | 用途 |
|------|------|------|
| fastapi | 0.139.0 | 後端 Web 框架，提供 `/api` 路由與前端靜態檔服務 |
| uvicorn | 0.51.0 | ASGI 伺服器，於 `127.0.0.1` 前景執行 |
| websockets | 16.0 | `/ws/log` 即時執行訊息推播 |
| pydantic | 2.13.4 | API 請求／回應資料驗證 |
| pyaedt | 1.2.0 | Ansys AEDT Python 控制介面（`ansys.aedt.core`） |

## 維護者：開發模式

需要 Node.js 18 以上：

```bat
dev.bat
```

- 後端 `127.0.0.1:8010`（`--reload`，另開視窗）
- 前端 Vite dev server `127.0.0.1:5180`（熱更新，經 proxy 轉發 `/api` 與 `/ws`）

前端改完後，**發布前務必重新建置並提交 `frontend/dist`**，否則使用者以「Code → Download ZIP」下載的 Source ZIP 會缺少前端而無法啟動：

```bat
cd frontend
npm ci
npm run build
```

## 目錄結構

```text
funnel-via-web/
├─ start.bat                     一般使用者啟動（UTF-8 無 BOM）
├─ start.ps1                     production 啟動邏輯（UTF-8 with BOM）
├─ dev.bat / dev.ps1             維護者開發模式
├─ backend/
│  ├─ app/
│  │  ├─ main.py                 FastAPI：/api、/ws/log，最後掛載 frontend/dist
│  │  └─ core.py                 疊構解析與漏斗分段計算
│  ├─ requirements.lock.txt      已實測的套件版本
│  └─ .venv/                     首次啟動自動建立（不進版控）
└─ frontend/
   ├─ src/                       React + Three.js 原始碼
   ├─ package-lock.json
   └─ dist/                      production 建置產物（必須進版控）
```

## 隱私

服務只綁定 `127.0.0.1`，不對外網開放；疊構、座標與專案資料皆在本機處理，**不會上傳**。唯一的網路行為是首次啟動時下載 Python 套件。
