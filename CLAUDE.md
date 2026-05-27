# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

第七史詩 (Epic Seven) Windows 版自動刷商店工具。通過 Windows 原生 API 操作遊戲視窗，使用圖像識別自動在秘密商店中尋找並購買聖約書籤和神秘書籤。

## Build & Run

- **執行**: `python main.py`
- **打包 EXE**: `pyinstaller -F -w -i main.ico main.py`
- **依賴安裝**: `pip install -r requirements.txt`
- Python 版本: 3.9.10

## Dependencies

- **PyQt6** (6.3.0) — GUI 框架
- **pywin32** (>=305) — Windows API（截圖、視窗操作、滑鼠控制）
- **aircv** (1.4.6) — 基於 OpenCV 的模板匹配圖像識別
- **numpy** (>=1.22.1) — 圖像陣列處理

## Architecture

單文件應用 (`main.py`)，包含兩個核心類：

- **`Worker`** (QThread) — 後台線程執行自動化邏輯。通過 `PrintWindow` 截圖 → `aircv` 模板匹配定位目標 → `PostMessage` 發送點擊。使用 PyQt Signal 與 UI 通信。
- **`Ui_Main`** (QWidget) — GUI 佈局與事件處理。UI 原始定義在 `main.ui`，由 `pyuic6` 生成 Python 代碼。

### Windows 交互層

工具函數提供兩種操作模式，通過 `config.json` 的 `foreground_mode` 切換：

- **背景模式** (`false`)：`PrintWindow` 截圖（視窗可被遮擋）+ `PostMessage` 點擊（不佔用滑鼠）
- **前景模式** (`true`)：`PrintWindow` 截圖 + `win32api.mouse_event` 點擊（佔用滑鼠，保證可靠）

### 自動化流程

`Worker.run()` 的核心循環：截圖 → 搜索聖約/神秘書籤位置 → 點擊購買 → 刷新商店（消耗天空石） → 重複直到達成目標次數或資源耗盡。支持三種模式：按聖約次數、按神秘次數、按天空石消耗量停止。

### 多語言支持

`img/` 目錄下按語言後綴存放模板圖片（`-zh-TW`、`-zh-CN`、`-en-US`），遊戲語言在 `config.json` 中配置。

## Configuration

`config.json` 字段：
- `window_title` — 遊戲視窗標題（預設 `"Epic Seven"`）
- `e7_language` — 遊戲語系（`zh-TW`、`zh-CN`、`en-US`）
- `foreground_mode` — `false` 背景不佔滑鼠 / `true` 佔用滑鼠（降級模式）
