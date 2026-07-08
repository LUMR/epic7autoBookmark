# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

第七史詩 (Epic Seven) 自動刷商店工具，支援兩種操作模式並可經 `config.json` 切換：**Windows 模式**（BitBlt/MSS 截圖 + SendInput 滑鼠，操作 PC 遊戲視窗）與 **ADB 模式**（操作安卓模擬器/真機，免管理員、不佔用實體滑鼠）。兩種模式透過統一的 `DeviceBackend` 抽象隔離平台差異，上層用 OpenCV 模板匹配自動在秘密商店中尋找並購買聖約書籤和神秘書籤。

> 📌 `README.md` 面向終端使用者（安裝/使用/設定簡介），本檔面向開發（完整架構與模組細節）。兩者如有出入，以本檔（CLAUDE.md）為準。

## Build & Run

- **執行**: `python main.py`（Windows 模式自動提權；ADB 模式免管理員。依 `config.json` 的 `platform` 決定）
- **打包 EXE**: `pyinstaller -F -w -i main.ico --hidden-import=win32api --hidden-import=win32gui --hidden-import=win32ui --hidden-import=win32con --collect-all PyQt6 main.py`
- **依賴安裝**: `pip install -r requirements.txt`
- Python 版本: 3.9+

## Test Files

- `tests/` — pytest 單元/整合測試，涵蓋 matcher、config、state、logger、coords、constants、flow、device、fakes、capture 等純邏輯層；IO/GUI 層靠手動驗證。執行全部：`pytest`；單一檔案：`pytest tests/test_config.py`；單一測試：`pytest tests/test_device.py::TestClass::test_method`。`fakes.py` 提供 `FakeDevice` 測試替身（device/flow 測試專用）。
- `tools/roi_helper.py` — 互動式框選商店區域，產出 `config.json` 的 ROI 座標 `[x,y,w,h]`。

## Architecture

多模組架構，核心流程為：GUI 啟動 → Worker 線程 → 狀態機驅動的 ShopFlow。

### 模組職責

| 模組 | 職責 |
|------|------|
| `main.py` | 入口：依 `platform` 決定提權（僅 Windows 模式）+ PyQt6 啟動 |
| `gui.py` | PyQt6 GUI（手寫 UI，非 .ui 生成），管理 Worker 生命週期 |
| `worker.py` | QThread 後台線程：`create_device(config)` 組裝設備、啟動 ShopFlow、通過 Signal 更新 UI |
| `config.py` | `AppConfig` dataclass，從 `config.json` 加載，支持舊欄位名映射 |
| `constants.py` | 全域常量：書籤價格、座標偏移、滑動座標、模式相關金幣閾值 |
| `automation/state.py` | `ShopState` 枚舉 + `ShopContext` dataclass（狀態機 + 運行時上下文，持有 `device: DeviceBackend`） |
| `automation/flow.py` | `ShopFlow` 狀態機主體 + `wait_for`/`wait_for_gone`/`wait_for_stable` 輪詢函數 + `_click_until_found`/`_click_until_gone` 點擊輔助 |
| `automation/templates.py` | `TemplateManager` 多語言模板加載（語言後綴回退 + 快取） |
| `detection/matcher.py` | `TemplateMatcher` OpenCV 多尺度模板匹配（替代原 aircv），支持 ROI 限制 |
| `capture/bitblt.py` | BitBlt (GDI) 截圖，`_ReusableCapture` 會話復用 + `close_all()` 釋放 |
| `capture/mss_backend.py` | MSS 庫截圖（備用後端） |
| `input/sendinput.py` | SendInput 滑鼠事件（佔用實體滑鼠，需管理員權限） |
| `input/base.py` | `InputBackend` 抽象基類 + `scale_to_client()` 參考座標轉換純函數 |
| `device/base.py` | `DeviceBackend` 抽象基類（capture/click/swipe 統一介面）+ 純函數（wm size/devices 解析、座標縮放、serial 選擇）+ `DeviceError` |
| `device/windows.py` | `WindowsDeviceBackend`（組合 capture+input+scale_to_client）+ `find_game_window` |
| `device/adb_client.py` | `AdbClient`：adb 子進程封裝（路徑定位、connect、devices、exec-out screencap、input tap/swipe） |
| `device/adb.py` | `AdbDeviceBackend`：ADB 模式後端（screencap 截圖 + 縮放點擊） |
| `device/humanize.py` | 人性化純函數（jitter/bezier/ease/random_gap/roll）+ `HumanizeSettings` dataclass,兩後端與 flow 共用 |
| `device/__init__.py` | `create_device(config)` 工廠：依 `platform` 建立 Windows/ADB 後端 |
| `logger.py` | 雙輸出日誌：帶時間戳的日誌檔案 + Qt Signal（GUI 顯示） |

### 狀態機流程

`ShopFlow.run()` 的狀態循環：`SCANNING` → 檢測書籤位置 → `BUYING_COVENANT`/`BUYING_MYSTIC` → `SWIPING`（滾動商店列表）→ `REFRESHING`（消耗 3 天空石刷新）→ 重複。三種停止條件：按聖約次數、按神秘次數、按天空石消耗量。

### 座標系統

所有座標基於 1920×1080 參考解析度（`capture.REF_WIDTH/REF_HEIGHT`）。flow 與 matcher 完全以參考解析度座標運作，平台差異由 `DeviceBackend` 內部吸收：Windows 後端用 `scale_to_client()` 映射到視窗客戶區；ADB 後端依設備實際解析度（`adb shell wm size`）按比例縮放。所有後端的 `capture()` 恆輸出 (1080,1920) BGR，`click/swipe` 吃參考座標，故模板、ROI、`constants` 座標跨平台零改動複用。

### 多語言模板

`img/` 目錄下按語言後綴存放模板圖片（`buyConfirmButton-zh-TW.png`）。`TemplateManager` 優先加載 `{name}-{lang}.png`，不存在時回退到 `{name}.png`。書籤位置模板（`covenantLocation.png`、`mysticLocation.png`）為語言通用。注意：`cv2.imread` 不支持中文路徑，模板加載使用 `np.fromfile` + `cv2.imdecode` 替代。

### 設備後端（DeviceBackend）

`create_device(config)` 依 `config.platform` 建立設備後端，統一 `capture()/click()/swipe()/prepare()/close()` 介面，flow 只依賴此介面、與平台無關：

- **Windows 模式** (`platform=windows`)：`WindowsDeviceBackend` 組合 `capture_window()`（BitBlt/MSS）+ SendInput。`capture_method`（`auto`/`bitblt`/`mss`）配置截圖方式。
- **ADB 模式** (`platform=adb`)：`AdbDeviceBackend` 透過 `AdbClient` 呼叫 adb（`exec-out screencap` 截圖、`input tap/swipe` 輸入）。`adb_screenshot_method` 為預留擴展點（目前 `screencap`）。

所有後端 `capture()` 恆輸出 BGR ndarray (1920×1080)；點擊吃參考解析度座標，由後端內部縮放。`capture/` 與 `input/` 套件為 Windows 後端所用，上層不再直接呼叫。

### 人性化（降低機器特徵）

點擊/滑動的位置抖動、軌跡與時序隨機化由各後端吸收（共用純函數集中於 `device/humanize.py`），flow 僅負責節奏（`short_sleep` 抖動擴大 + 主循環 `maybe_pause`）。Windows 後端生成貝茲曲線游標軌跡 + 加減速；ADB 後端務實方案（位置/起終點抖動 + 時序隨機，軌跡維持系統直線）。`humanize_enabled=false` 可完全關閉、位元級退回舊行為。

### 其他目錄

- `docs/superpowers/{plans,specs}/` — 設計文檔與實施計劃（如 ADB 模式設計/計劃），為架構決策來源，遇疑問可查。
- `legacy/` — 已歸檔的舊實驗腳本（`test_postmessage.py`、`test_printwindow.py` 等，對應早期 PostMessage/PrintWindow 方案）。**非活躍代碼，勿修改或當作參考實作。**
- `img/` — 模板圖片（詳見「多語言模板」）。執行 `main.exe` / `python main.py` 時需與 `config.json` 同目錄。

## Configuration

`config.json` 由 `AppConfig` dataclass 管理，新欄位均有默認值，舊版配置文件可直接使用。舊欄位名自動映射（如 `e7_language` → `language`；`foreground_mode` 為已廢棄欄位，會被忽略）。

> ⚠️ **倉庫隨附的 `config.json` 本身仍是舊版**（僅含 `e7_language`/`foreground_mode`/`default_*`，未含 `platform`/`capture_method`/`adb_*` 等新欄位）—— 這**不是 bug**：靠默認值與別名映射即可正常運行，預設即純 Windows 模式（`platform=windows`）。要啟用 ADB 模式，需自行加入 `platform: "adb"` 與相關 `adb_*` 欄位。

關鍵欄位：

- `window_title` — 遊戲視窗標題（預設 `"第七史诗"`）
- `language` — 遊戲語系（`zh-TW`、`zh-CN`、`en-US`）
- `capture_method` — 截圖方式（`auto`、`bitblt`、`mss`）
- `input_backend` — 輸入後端（Windows 模式，目前僅 `sendinput`）
- `platform` — 操作模式主切換（`windows` / `adb`），預設 `windows`
- `adb_path` / `adb_serial` / `adb_connect` — ADB 模式：adb 路徑（`null`=用系統 PATH）、設備 serial（`null`=自動取唯一設備，多設備報錯）、連線位址如 `127.0.0.1:7555`（`null`=不 connect）
- `adb_screenshot_method` — ADB 截圖方式（預留擴展點，目前 `screencap`）
- `match_threshold_*` — 各類元素的模板匹配置信度閾值（location=0.9, button=0.85, confirm=0.9, refresh=0.8）
- `scan_roi` / `button_roi` — 模板匹配搜尋區域 `[x,y,w,h]`（可選，`null`=全圖）。用 `tools/roi_helper.py` 框選；書籤掃描與按鈕搜尋分開配置
- `short_sleep_base` / `wait_timeout` / `wait_timeout_long` — 時序參數（預設 1.0 / 5.0 / 8.0 秒）
- `max_retry` — 重試次數上限（預設 20）
- `swipe_fail_limit` — 連續滑動無變化（商店瀏覽完畢）達此閾值則刷新商店（預設 5）
- `humanize_enabled` — 人性化（降低機器特徵）總開關,預設 `true`;`false` 位元級退回舊行為
- `humanize_jitter_px` / `humanize_swipe_jitter_px` — 點擊/滑動起終點的位置抖動半徑（參考解析度 px）
- `humanize_curve_strength` / `humanize_move_steps` — 僅 Windows:貝茲軌跡弧度與取樣點數
- `humanize_pause_chance` / `humanize_pause_duration` / `humanize_pause_spread` — 主循環偶爾停頓的機率與時長
- `humanize_double_click_spread` / `humanize_swipe_duration_spread` — 雙擊間隔與滑動時長的隨機抖動（秒）

## Git

- 提交代码时不要署名
