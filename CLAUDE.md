# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

第七史詩 (Epic Seven) Windows 版自動刷商店工具。通過 Windows 原生 API 操作遊戲視窗，使用 OpenCV 模板匹配自動在秘密商店中尋找並購買聖約書籤和神秘書籤。

## Build & Run

- **執行**: `python main.py`（需要管理員權限，程式會自動提權）
- **打包 EXE**: `pyinstaller -F -w -i main.ico --hidden-import=win32api --hidden-import=win32gui --hidden-import=win32ui --hidden-import=win32con --collect-all PyQt6 main.py`
- **依賴安裝**: `pip install -r requirements.txt`
- Python 版本: 3.9+

## Test Files

- `tests/` — pytest 單元/整合測試，執行 `pytest`。涵蓋 matcher、config、state、logger、coords、constants、flow 等純邏輯層；IO/GUI 層靠手動驗證。
- `tools/roi_helper.py` — 互動式框選商店區域，產出 `config.json` 的 ROI 座標 `[x,y,w,h]`。

## Architecture

多模組架構，核心流程為：GUI 啟動 → Worker 線程 → 狀態機驅動的 ShopFlow。

### 模組職責

| 模組 | 職責 |
|------|------|
| `main.py` | 入口：管理員提權 + PyQt6 啟動 |
| `gui.py` | PyQt6 GUI（手寫 UI，非 .ui 生成），管理 Worker 生命週期 |
| `worker.py` | QThread 後台線程：組裝組件、啟動 ShopFlow、通過 Signal 更新 UI |
| `config.py` | `AppConfig` dataclass，從 `config.json` 加載，支持舊欄位名映射 |
| `constants.py` | 全域常量：書籤價格、座標偏移、滑動座標、模式相關金幣閾值 |
| `automation/state.py` | `ShopState` 枚舉 + `ShopContext` dataclass（狀態機 + 運行時上下文） |
| `automation/flow.py` | `ShopFlow` 狀態機主體 + `wait_for`/`wait_for_gone`/`wait_for_stable` 輪詢函數 + `_click_until_found`/`_click_until_gone` 點擊輔助 |
| `automation/templates.py` | `TemplateManager` 多語言模板加載（語言後綴回退 + 快取） |
| `detection/matcher.py` | `TemplateMatcher` OpenCV 多尺度模板匹配（替代原 aircv），支持 ROI 限制 |
| `capture/bitblt.py` | BitBlt (GDI) 截圖，`_ReusableCapture` 會話復用 + `close_all()` 釋放 |
| `capture/mss_backend.py` | MSS 庫截圖（備用後端） |
| `input/sendinput.py` | SendInput 滑鼠事件（佔用實體滑鼠，需管理員權限） |
| `input/base.py` | `InputBackend` 抽象基類 + `scale_to_client()` 參考座標轉換純函數 |
| `logger.py` | 雙輸出日誌：帶時間戳的日誌檔案 + Qt Signal（GUI 顯示） |

### 狀態機流程

`ShopFlow.run()` 的狀態循環：`SCANNING` → 檢測書籤位置 → `BUYING_COVENANT`/`BUYING_MYSTIC` → `SWIPING`（滾動商店列表）→ `REFRESHING`（消耗 3 天空石刷新）→ 重複。三種停止條件：按聖約次數、按神秘次數、按天空石消耗量。

### 座標系統

所有座標基於 1920×1080 參考解析度（`capture.REF_WIDTH/REF_HEIGHT`）。`scale_to_client()`（`input/base.py`）在運行時映射到實際視窗客戶區大小。模板匹配結果和自動化流程中的座標均為參考解析度座標。

### 多語言模板

`img/` 目錄下按語言後綴存放模板圖片（`buyConfirmButton-zh-TW.png`）。`TemplateManager` 優先加載 `{name}-{lang}.png`，不存在時回退到 `{name}.png`。書籤位置模板（`covenantLocation.png`、`mysticLocation.png`）為語言通用。注意：`cv2.imread` 不支持中文路徑，模板加載使用 `np.fromfile` + `cv2.imdecode` 替代。

### 截圖後端

`capture_window()` 支持三種模式（`config.json` 中 `capture_method` 配置）：`auto`（BitBlt 優先，失敗回退 MSS）、`bitblt`、`mss`。所有後端統一輸出 BGR ndarray (1920×1080)。配置透過 `ShopContext.capture_method` 傳遞至 flow 的所有截圖調用。

## Configuration

`config.json` 由 `AppConfig` dataclass 管理，新欄位均有默認值，舊版配置文件可直接使用。舊欄位名自動映射（如 `e7_language` → `language`）。關鍵欄位：

- `window_title` — 遊戲視窗標題（預設 `"第七史诗"`）
- `language` — 遊戲語系（`zh-TW`、`zh-CN`、`en-US`）
- `capture_method` — 截圖方式（`auto`、`bitblt`、`mss`）
- `input_backend` — 輸入後端（目前僅 `sendinput`）
- `match_threshold_*` — 各類元素的模板匹配置信度閾值（location=0.9, button=0.85, confirm=0.9, refresh=0.8）
- `scan_roi` / `button_roi` — 模板匹配搜尋區域 `[x,y,w,h]`（可選，`null`=全圖）。用 `tools/roi_helper.py` 框選；書籤掃描與按鈕搜尋分開配置
- `short_sleep_base` / `wait_timeout` / `wait_timeout_long` — 時序參數（預設 1.0 / 5.0 / 8.0 秒）
- `max_retry` — 重試次數上限（預設 20）
- `swipe_fail_limit` — 連續滑動失敗退出閾值（預設 5）

## Git

- 提交代码时不要署名
