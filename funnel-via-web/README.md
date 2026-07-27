# HFSS 3D 漏斗狀 Via 網頁版建模工具 (Web App)

此工具由虎門科技資深技術工程師 Jeff Hong 洪敬傑提供。

## 簡介
這是一個將原本基於 Tkinter 的 `funnel_via_gui.py` 轉換為現代化網頁應用程式的版本。前端使用 React + Vite 並搭配 Three.js 提供即時的 3D 幾何預覽，後端使用 FastAPI 與 PyAEDT 負責實際的模型控制與生成。

## 系統需求 (預先下載安裝)
請確保您的系統已安裝以下軟體：
1. **Ansys Electronics Desktop (AEDT)**：需為已安裝之正式版本，以利透過 PyAEDT 進行控制。
2. **Python 3.9 ~ 3.12**：後端環境執行需要。
3. **Node.js 18+**：前端環境執行需要。
4. **uv (選擇性，但強烈建議)**：高效的 Python 套件管理工具，若全域未安裝，啟動腳本將自動在虛擬環境內幫您安裝。

## 操作說明
1. 進入此資料夾 `D:\AI Development\Build funnel Via Toolkit\funnel-via-web`。
2. 雙擊執行 `start.bat`。
3. 腳本會自動為您安裝所需的 Python 及 Node.js 套件，並分別啟動前端 (Port 5180) 與後端 (Port 8010) 伺服器。
4. 啟動完成後，會自動在您的預設瀏覽器開啟應用程式介面 `http://localhost:5180`。
5. 在網頁介面中輸入您的 AEDT 版本，點擊「連線 AEDT」。
6. 修改疊構與參數，中間的 3D 視窗將會即時顯示漏斗 Via 的預覽形狀。
7. 設定完成後，點擊「建立漏斗 Via」，工具將會在 AEDT 中生成對應的幾何物件。
