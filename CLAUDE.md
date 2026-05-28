# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

第七史詩 (Epic Seven) Windows 版自動刷商店工具。通過 Windows 原生 API 操作遊戲視窗，使用圖像識別自動在秘密商店中尋找並購買聖約書籤和神秘書籤。

## Build & Run

- **執行**: `python main.py`（需要管理員權限，程式會自動提權）
- **打包 EXE**: `pyinstaller -F -w -i main.ico --hidden-import=win32api --hidden-import=win32gui --hidden-import=win32ui --hidden-import=win32con --collect-all PyQt6 main.py`
- **依賴安裝**: `pip install -r requirements.txt`
- Python 版本: 3.9+

## Dependencies

- **PyQt6** — GUI 框架
- **pywin32** — Windows API（截圖、視窗操作、滑鼠控制）
- **aircv** — 基於 OpenCV 的模板匹配圖像識別
- **numpy** — 圖像陣列處理
- **opencv-python** (cv2) — 圖像縮放、畫面差異比對

## Architecture

單文件應用 (`main.py`, ~800 行)，包含兩個核心類：

- **`Worker`** (QThread) — 後台線程執行自動化邏輯。截圖 → 模板匹配定位 → 滑鼠點擊。使用 PyQt Signal 與 UI 通信。
- **`Ui_Main`** (QWidget) — GUI 佈局與事件處理。手寫 PyQt6 UI 代碼（非 .ui 生成）。

### Windows 交互層

- **截圖**：`capture_window()` 使用桌面 DC + `BitBlt` 複製客戶區域像素（需要視窗可見）
- **點擊**：`click_at()` / `double_click_at()` 使用 `win32api.mouse_event` 發送實體滑鼠事件（佔用滑鼠）
- **滑動**：`swipe_at()` 分步模擬滑鼠拖拽，用於滾動商店列表
- **座標縮放**：`_scale()` 將 1920×1080 參考座標映射到實際視窗大小

### 管理員提權

啟動時通過 `ctypes.windll.shell32.ShellExecuteW(..., "runas", ...)` 自動請求 UAC 提權。

### 自動化流程

`Worker.run()` 的核心循環：截圖 → 搜索聖約/神秘書籤位置 → 雙擊商品 → 等待購買按鈕出現 → 點擊購買 → 滑動商店列表 → 刷新商店（消耗天空石） → 重複。支持三種停止條件：按聖約次數、按神秘次數、按天空石消耗量。

### 輪詢確認模式

`wait_for()` 函數提供帶超時的輪詢機制，用於等待按鈕出現/消失，替代固定 `time.sleep`。

### 多語言支持

`img/` 目錄下按語言後綴存放模板圖片（`-zh-TW`、`-zh-CN`、`-en-US`），遊戲語言在 `config.json` 中配置。

## Configuration

`config.json` 字段：
- `window_title` — 遊戲視窗標題（預設 `"Epic Seven"`）
- `e7_language` — 遊戲語系（`zh-TW`、`zh-CN`、`en-US`）
- `foreground_mode` — 保留配置項，目前代碼始終使用前景模式
- `default_money` / `default_stone` / `default_covenant` / `default_mystic` / `default_stone_usage` — UI 輸入框預設值

## Test Files

`test_*.py` 為獨立的調試/驗證腳本，非單元測試框架，直接 `python test_xxx.py` 執行。

## Git
- 提交代码时不要署名