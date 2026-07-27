# HFSS Funnel Via Toolkit

以 PyAEDT 建立 HFSS 3D Layout 無法直接產生的漏斗狀堆疊雷射微孔（stacked laser via）。工具以多段圓錐台沿 Z 軸堆疊，並提供 GUI 參數設定。

## 主要功能

- 設定多層板 stackup。
- 設定 layer transition 與 via 寬度。
- 產生多段漏斗狀 via 幾何。
- 直接連接目前開啟的 AEDT／HFSS 專案。

## 使用環境

- Ansys Electronics Desktop（含 HFSS）
- Python 3
- PyAEDT：`pip install pyaedt`
- Tkinter（Python 內建）

## 使用方式

1. 開啟 AEDT，載入 HFSS 專案與設計。
2. 執行 `python funnel_via_gui.py`，或使用已建立的執行檔。
3. 輸入 stackup、layer transition 與 via 參數。
4. 執行建模並確認 AEDT 幾何結果。

## 公開範圍

本 Repository 以腳本與功能展示為主。AEDT 專案與模擬結果不列入版本控制。

如需完整商用版本、AEDT 版本相容性調整或客製化整合，請來信洽詢。

此工具由虎門科技資深技術工程師 Jeff Hong 洪敬傑提供
