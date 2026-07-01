# epic7autoBookmark

第七史詩刷商店的小工具，支援 **Windows 模式**（操作 PC 遊戲視窗）與 **ADB 模式**（操作安卓模擬器/真機）兩種模式。

![image](https://github.com/steven010116/epic7autoBookmark/assets/24381832/526e78b9-df97-4500-9758-55f514eed883)

## 一、環境

0. 作業系統
   - **Windows 模式**：Windows 10/11（需管理員權限，程式會自動提權）
   - **ADB 模式**：Windows / macOS / Linux 皆可（免管理員）
1. 第七史詩
   - Windows 模式：PC 版，遊戲解析度設為 1920×1080
   - ADB 模式：安卓模擬器或真機，解析度建議 1920×1080（或 16:9 同比例）
2. Python 3.9+（從原始碼執行時）
3. `config.json`（見下方說明）

## 二、config.json 說明

透過 `platform` 切換操作模式：

| 欄位 | 說明 | 預設 |
|------|------|------|
| `platform` | `windows` 或 `adb` | `windows` |
| `window_title` | 遊戲視窗標題（Windows 模式用，可在工作管理員確認） | `"第七史诗"` |
| `language` | 遊戲語系：`zh-TW` / `zh-CN` / `en-US` | `zh-TW` |
| `capture_method` | Windows 截圖方式：`auto` / `bitblt` / `mss` | `auto` |

**ADB 模式**額外欄位：

| 欄位 | 說明 |
|------|------|
| `adb_path` | `adb.exe` 路徑；`null` 表示用系統 PATH |
| `adb_serial` | 設備 serial；`null` 自動取唯一設備（多設備會報錯） |
| `adb_connect` | 連線位址如 `"127.0.0.1:7555"`；`null` 表示不 connect |

ADB 模式最小設定範例：

```json
{
    "platform": "adb",
    "language": "zh-TW",
    "adb_connect": "127.0.0.1:7555"
}
```

> 舊欄位 `e7_language` 會自動映射為 `language`；`foreground_mode` 已廢棄，可移除。

## 三、使用方式

### 方式一：直接執行 EXE

1. 綠色按鈕 Code > Download ZIP 整包下載後解壓縮，放在同一個資料夾下，路徑建議為英數避免問題
2. 確認 `config.json` 內的參數正確
3. 開啟遊戲，進到秘密商店
4. 執行 `main.exe`（在 `dist/` 目錄下）
5. 選擇條件並輸入目標次數，按下開始

### 方式二：從原始碼執行

1. 安裝依賴：`pip install -r requirements.txt`
2. 執行：`python main.py`（Windows 模式自動提權；ADB 模式免管理員）

### 自行打包 EXE

1. 安裝 PyInstaller：`pip install pyinstaller`
2. 打包：`pyinstaller -F -w -i main.ico --hidden-import=win32api --hidden-import=win32gui --hidden-import=win32ui --hidden-import=win32con --collect-all PyQt6 main.py`（或 `python -m PyInstaller main.spec`）
3. 產出的 `dist/main.exe` 需與 `config.json` 和 `img/` 放在同一目錄下才能執行：
   ```
   資料夾/
   ├── main.exe
   ├── config.json
   └── img/
       ├── covenantLocation.png
       ├── mysticLocation.png
       ├── buyButton-zh-TW.png
       └── ...
   ```

## 四、運作原理

- **擷取畫面**：Windows 模式用 BitBlt(GDI)/MSS 截圖；ADB 模式用 `adb exec-out screencap`
- **圖像辨識**：OpenCV 模板匹配，自動定位書籤與按鈕位置（支援多語系模板）
- **執行點擊**：Windows 模式用 SendInput（佔用實體滑鼠，故需管理員權限）；ADB 模式用 `adb input tap`（不佔用實體滑鼠）
- 兩種模式經統一的 `DeviceBackend` 介面切換，商店流程邏輯共用
- 所有座標基於 1920×1080 參考解析度，不同視窗/設備解析度由後端自動縮放

> 想在不佔用實體滑鼠、不遮擋遊戲視窗的情況下掛機，請改用 **ADB 模式** 操作模擬器/真機。

## 五、特別感謝

Raven9527 - 自動點擊派遣功能
