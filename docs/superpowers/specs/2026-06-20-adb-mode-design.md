# ADB 模式支持設計

**日期:** 2026-06-20
**狀態:** 已確認設計,待撰寫實施計劃
**平台:** 模擬器 + 真機(解析度自動偵測),與 Windows 原生模式並存可切換

**Goal:** 在不改動模板、ROI、matcher、constants 的前提下,新增以 ADB 操作設備的模式,並與現有 BitBlt+SendInput 的 Windows 模式並存,透過 `config.json` 切換。

**Architecture:** 在 capture/input 之上引入統一的 `DeviceBackend` 門面,把「截圖 + 輸入 + 座標縮放 + 生命週期」收攏到一個介面;上層 flow 與平台無關,不再直接依賴 `hwnd` 與 Win32。

**Tech Stack:** Python 3.9+、PyQt6、OpenCV、pywin32、adb(子進程呼叫)、pytest

---

## 背景與目標

現有工具透過 Windows 原生 API 操作遊戲視窗:BitBlt/MSS 截圖 + SendInput 滑鼠輸入,需要管理員權限、佔用實體滑鼠、視窗須可見且在前台。ADB 模式以 `adb` 指令操作安卓設備(模擬器或真機),不需要管理員權限、不佔用實體滑鼠、視窗不必在前台。

目標是讓同一份 flow/匹配邏輯同時驅動兩種設備,使用者依 `config.json` 的 `platform` 欄位切換。

## 已確認的決策(設計約束)

1. **目標設備**:模擬器與真機兩者皆支援(USB / WiFi / 本機 `adb connect`)。
2. **與 Windows 模式關係**:並存,可切換。保留 Windows 原生模式,新增 ADB 模式。
3. **解析度**:不固定,運行時 `adb shell wm size` 自動偵測;所有座標經縮放處理。
4. **adb 程式定位**:`config.adb_path` 指定優先,未指定時 fallback 系統 `PATH`(打包與調試皆方便)。
5. **截圖/輸入實現**:純 adb 指令(`exec-out screencap` / `input tap`/`swipe`),但 `DeviceBackend` 介面設計好擴展點,未來可插 minicap/scrcpy 等高效後端。
6. **切換入口**:純 `config.json`(`platform` 欄位),GUI 起步不動。
7. **serial 選擇**:`config.adb_serial` 指定優先 → 否則 `adb devices` 取唯一設備 → 0 台報錯 / ≥2 台且未指定報錯。
8. **`adb_connect`**:可選。模擬器/WiFi 場景填 `host:port`(如 `127.0.0.1:7555`),工具自動 `adb connect`;留空則完全交給 `adb devices`。

## 核心問題:hwnd 滲透

現有架構中 `hwnd`(Windows 視窗句柄)滲透到多處:

- `capture_window(hwnd, method)` —— bitblt/mss 內部用 `win32gui`
- `InputBackend.click(hwnd, x, y)` —— sendinput 內部 `ClientToScreen`
- `scale_to_client(hwnd)` —— 靠 `win32gui.GetClientRect(hwnd)`
- `find_game_window()` —— `EnumWindows`
- `ShopContext.hwnd`
- `flow._init()` 直接呼叫 `win32gui.SetForegroundWindow(hwnd)`

ADB 模式沒有 hwnd,取而代之的是 device serial 與一套完全不同的截圖/輸入原語。因此「支援 ADB」的本質是在 capture/input 之下引入一層**設備抽象**,讓上層 flow 不再直接依賴 hwnd 與 Win32。

## 架構:統一 DeviceBackend 門面(方案 A)

將「截圖 + 輸入 + 座標縮放 + 生命週期」打包為單一 `DeviceBackend` 介面。flow 只持有 `device`,呼叫 `device.capture()` / `device.click(ref_x, ref_y)` / `device.swipe(...)`,完全看不到 hwnd 或 serial。

選擇方案 A 而非「target 泛化」或「config 字串分支」的理由:

- 座標縮放、前台激活等平台特定邏輯被一次收攏到 device 內,不再散落 flow。
- factory 依 `config.platform` 一次建立整組一致的後端,杜絕 capture/input 平台錯配。
- 「預留擴展點」最乾淨的形態:未來加高效截圖或新平台 = 新增一個 Backend 類。
- flow 有整合測試覆蓋,呼叫點的機械替換風險可控。

## 模組佈局

新增 `device/` 套件作為門面。現有 `capture/`、`input/` **保留不刪**(Windows 後端仍復用),上層不再直接呼叫。

```
device/
  __init__.py        # create_device(config) 工廠 + DeviceError
  base.py            # DeviceBackend 抽象基類 + 座標契約 + 純函數(縮放/wm size 解析)
  windows.py         # WindowsDeviceBackend(組合 bitblt/mss + sendinput + scale_to_client)
  adb.py             # AdbDeviceBackend(adb screencap/input + 動態縮放)
  adb_client.py      # AdbClient:adb 子進程封裝(路徑定位、exec-out、wm size、devices、tap/swipe)
```

**依賴方向**:`worker / flow` → `device` → (`capture`,`input`)。

| 檔案 | 動作 | 職責 |
|------|------|------|
| `device/__init__.py` | 新建 | `create_device(config)` 工廠 + `DeviceError` |
| `device/base.py` | 新建 | `DeviceBackend` 抽象基類、純函數(`parse_wm_size`、`parse_devices`、`scale_ref_to_device`) |
| `device/windows.py` | 新建 | `WindowsDeviceBackend`(組合現有 capture/input) |
| `device/adb_client.py` | 新建 | `AdbClient`(adb 子進程封裝) |
| `device/adb.py` | 新建 | `AdbDeviceBackend` |
| `automation/state.py` | 修改 | `hwnd` → `device`;移除 `capture_method` |
| `automation/flow.py` | 修改 | `input_backend` → `device`;截圖/點擊/前置改走 device;移除 win32gui 依賴 |
| `worker.py` | 修改 | `create_device(config)` 組裝;`device.close()` 收尾 |
| `config.py` | 修改 | 新增 `platform` / `adb_*` 欄位 + 校驗 |
| `main.py` | 修改 | 依 `platform` 決定是否提權 |
| `tests/test_device.py` | 新建 | device 層純邏輯 + factory + 縮放/解析單測 |
| `tests/test_flow*.py` | 修改 | mock 注入改為 `FakeDevice` |

## DeviceBackend 介面(`device/base.py`)

```python
class DeviceBackend(ABC):
    """統一設備門面。

    契約:
      - capture() 恆輸出 BGR ndarray,形狀 (1080, 1920, 3)。
      - click/swipe 吃「參考解析度座標」(基於 1920×1080),由實作內部縮放為設備實際座標。
      - 上層 flow 與平台無關。
    """

    @abstractmethod
    def capture(self) -> np.ndarray: ...                       # (REF_HEIGHT, REF_WIDTH, 3) BGR

    @abstractmethod
    def click(self, ref_x: float, ref_y: float) -> None: ...
    @abstractmethod
    def double_click(self, ref_x: float, ref_y: float) -> None: ...
    @abstractmethod
    def swipe(self, x1, y1, x2, y2, duration: float = 0.1) -> None: ...   # duration: 秒

    def prepare(self) -> None: ...          # 前置:Windows=SetForegroundWindow;ADB=連線健康檢查
    def close(self) -> None: ...            # 釋放:Windows=bitblt close_all;ADB=noop

    @property
    def resolution(self) -> tuple[int, int]: ...   # 設備實際解析度(日誌/偵錯用)
```

關鍵變化:`click/swipe` 簽名**不再有 hwnd 參數,直接吃參考座標**;`scale_coords` 整個消失(縮放內化到各實作)。`prepare()` 收進 `flow._init()` 現有的 `SetForegroundWindow`。

`base.py` 同時提供純函數(無副作用、易單測):

- `parse_wm_size(text: str) -> tuple[int, int]`:解析 `Physical size: 1920x1080`。
- `parse_devices(text: str) -> list[str]`:解析 `adb devices` 輸出,過濾 `offline`/`unauthorized`,回傳可用 serial 列表。
- `scale_ref_to_device(ref_x, ref_y, dev_w, dev_h) -> tuple[int, int]`:參考座標 → 設備座標。

## 座標系統與解析度偵測(模板零改動複用)

| | capture 輸出 | 點擊座標轉換 |
|---|---|---|
| **Windows** | BitBlt/MSS 截客戶區 → resize 到 (1080,1920) | 沿用 `scale_to_client(hwnd)` 讀 `GetClientRect`(行為不變,搬進 WindowsDeviceBackend) |
| **ADB** | `adb exec-out screencap -p` 原圖 → resize 到 (1080,1920) | 參考座標 ×(W/1920, H/1080)。W/H 啟動時 `wm size` 取得並快取 |

因為所有後端 capture 恆輸出 (1080,1920),**matcher、`scan_roi`/`button_roi`、`img/` 模板、`constants.py` 的 `SWIPE_*`/`BUY_CLICK_OFFSET_*` 全部零改動**。matcher 回傳的 `center` 即參考座標,直接餵 `device.click`,座標鏈天然閉合。

> 真機若有黑邊/狀態列 letterbox,本階段不處理(YAGNI),記為已知限制,日後真機實測發現問題再補。

## WindowsDeviceBackend(`device/windows.py`)

組合現有 `capture` 與 `input`,行為與舊版完全一致:

- `__init__(self, hwnd, capture_method)`:持有 hwnd 與 capture_method。
- `capture()`:`capture_window(hwnd, capture_method)`。
- `click/double_click/swipe`:內部先 `scale_to_client(hwnd, ref_x, ref_y)` 換成客戶區座標,再委託 `SendInputBackend` 對應方法(傳入 hwnd)。
- `prepare()`:`win32gui.SetForegroundWindow(hwnd)`(容錯,沿用現有 try/except)。
- `close()`:`capture.bitblt.close_all()`。
- `resolution`:`GetClientRect` 回傳的客戶區尺寸。

## AdbClient(`device/adb_client.py`)

封裝所有 adb 子進程呼叫,遮蔽 subprocess 細節。

| 能力 | 實現 |
|---|---|
| **adb 路徑定位** | `config.adb_path` 指定優先 → 否則 PATH 找 `adb`(Windows 補 `.exe`)。找不到 → `DeviceError` |
| **連線** | 若 `config.adb_connect` 有值 → `adb connect <host>` |
| **serial 選擇** | `config.adb_serial` 指定 → 用;否則 `adb devices` 解析:恰 1 台 → 用;0 台 → 報錯;≥2 台 → 報錯「多設備請設 adb_serial」 |
| `exec_out(args)` | `adb -s <serial> exec-out <args>` → bytes(二進制安全) |
| `run(args)` | `adb -s <serial> shell <args>` → stdout 文字 |
| `wm_size()` | `shell wm size` → 經 `parse_wm_size` 回 `(w, h)` |
| `tap/swipe` | `shell input tap x y` / `shell input swipe x1 y1 x2 y2 <ms>` |

所有 `subprocess.run` 捕獲異常 → `DeviceError`(含 stderr 與中文訊息)。超時預設 ~10s。

## AdbDeviceBackend(`device/adb.py`)

```python
class AdbDeviceBackend(DeviceBackend):
    def __init__(self, client: AdbClient):
        self._client = client
        self._w, self._h = client.wm_size()           # 啟動偵測一次,快取
        self._sx, self._sy = self._w / REF_WIDTH, self._h / REF_HEIGHT

    def capture(self):
        png = self._client.exec_out("screencap -p")   # exec-out: 二進制透傳,無 \r\n 污染
        img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
        if (self._w, self._h) != (REF_WIDTH, REF_HEIGHT):
            img = cv2.resize(img, (REF_WIDTH, REF_HEIGHT))
        return img

    def click(self, ref_x, ref_y):
        dx, dy = scale_ref_to_device(ref_x, ref_y, self._w, self._h)
        self._client.tap(dx, dy)

    def double_click(self, ref_x, ref_y):             # adb 無原生雙擊 → 兩次 tap
        self.click(ref_x, ref_y); time.sleep(0.05); self.click(ref_x, ref_y)

    def swipe(self, x1, y1, x2, y2, duration=0.1):    # 秒 → ms
        sx1, sy1 = scale_ref_to_device(x1, y1, self._w, self._h)
        sx2, sy2 = scale_ref_to_device(x2, y2, self._w, self._h)
        self._client.swipe(sx1, sy1, sx2, sy2, int(duration*1000))

    def prepare(self): ...      # 確認設備在線、解析度已知(已在 __init__ 偵測)
    def close(self): ...        # noop
```

> **為何用 `exec-out` 而非 `shell screencap`**:shell 模式會把 PNG 中的 `\n` 轉成 `\r\n` 損壞圖片;`exec-out` 二進制透傳,可靠。
> **`double_click`**:flow 的點擊輔助全部走 `double_click`,ADB 模擬為兩次 `tap` 以保持行為等價。

## 配置變更(`config.py` + `config.json`)

新增欄位,**全部有預設值,舊 config.json 直接相容**(預設 `windows` 維持原行為):

```python
platform: str = "windows"                  # windows / adb —— 主切換
adb_path: str | None = None                # None = 用 PATH
adb_serial: str | None = None              # None = 自動取唯一設備
adb_connect: str | None = None             # 如 "127.0.0.1:7555",模擬器/WiFi 連線;None=不 connect
adb_screenshot_method: str = "screencap"   # 預留擴展點(screencap / 未來 minicap...)
```

- 新增 `_VALID_PLATFORMS = ("windows","adb")`、`_VALID_ADB_SCREENSHOT_METHODS = ("screencap",)`,`validate()` 校驗。
- `platform == "windows"`:`capture_method`/`input_backend` 沿用現有邏輯。
- `platform == "adb"`:`create_device` 接管,`capture_method`/`input_backend` 忽略(文件註明)。
- `adb_screenshot_method` 是「預留擴展點」落地位置 —— 本階段只實作 `screencap`。

## 組裝(`worker.py`)

```python
config = AppConfig.load()
logger  = ShopLogger(self.emitLog)
device  = create_device(config)        # 依 platform 建 Windows/ADB 後端(內部做視窗查找/連線/serial)
ctx     = ShopContext(device=device, mode=..., expect_num=..., money=..., stone=...)
templates, matcher = TemplateManager(...), TemplateMatcher()
flow     = ShopFlow(ctx, templates, matcher, device, logger, config)   # input_backend → device
result   = flow.run()
...
finally: device.close()                # 替代 close_all()
```

`create_device(config)` 分派:

- `platform=="windows"` → `find_game_window(config.window_title)`(失敗報錯)→ `WindowsDeviceBackend(hwnd, config.capture_method)`。
- `platform=="adb"` → `AdbClient(config)`(路徑定位/連線/serial)→ `AdbDeviceBackend(client)`。

## ShopContext 與 flow 改動

**ShopContext**(`automation/state.py`):`hwnd: int` → `device: DeviceBackend`,移除 `capture_method`(內移到 WindowsDeviceBackend)。`stop()`/`should_continue`/統計欄位均不涉及 hwnd,不動。

**flow.py**(機械替換):

- `__init__` 參數 `input_backend` → `device`;移除 `from capture import capture_window` 與 `import win32gui`。
- 所有 `capture_window(ctx.hwnd, ctx.capture_method)` → `ctx.device.capture()`(scanning/swiping/refreshing + 模組級 `wait_for`/`wait_for_gone`/`wait_for_stable`)。
- 點擊從 `cx,cy = self.input.scale_coords(ctx.hwnd,*ref); self.input.double_click(ctx.hwnd,cx,cy)` → **`self.device.double_click(*ref)`**(參考座標直傳,縮放內化)。swipe 同理,座標直傳、`duration` 維持秒。
- `_init()` 的 `win32gui.SetForegroundWindow(ctx.hwnd)` → `self.device.prepare()`。

`SWIPE_DURATION`(秒)與 `device.swipe(duration=秒)` 單位一致,常量無需改。

## main.py 提權

ADB 模式**不需要管理員權限**(adb 為使用者級,且不佔用實體滑鼠)。改為:**先 `AppConfig.load()` 讀 `platform`**,`platform=="windows"` 才走提權;`platform=="adb"` 跳過,避免每次彈 UAC。(以管理員身份跑 ADB 模式無害,僅非必要。)

## 錯誤處理

| 場景 | 處理 |
|---|---|
| `create_device` 階段:視窗找不到 / adb 路徑缺失 / 無設備 / 多設備未指定 / `wm size` 解析失敗 | 拋 `DeviceError`(中文訊息)→ worker 的 `except` 捕獲 → `emitLog` 顯示 → `isError` |
| 運行中 adb 斷線 | capture 拋錯冒泡 → worker 捕獲停止(與 Windows 截圖失敗行為一致) |
| 設備掉線自動重連 | YAGNI,本階段不做,掉線即停(記為已知限制) |

## 測試策略(均不需真實 Android 設備)

- **flow 整合測試**:現有 mock「capture_window + input_backend」改為注入 `FakeDevice`(實作 DeviceBackend:`capture()` 回固定圖、`click/swipe` 記錄座標)。既有用例邏輯不變,只換注入方式。
- **device 層純邏輯單測**(重點,易測):
  - `parse_wm_size`:`"Physical size: 1280x720"` → `(1280,720)`
  - `parse_devices` + serial 選擇:1 台自動取 / 0 台報錯 / ≥2 台報錯
  - `scale_ref_to_device`:`dev=1280x720` 時 `(960,540)` → `(640,360)`
  - factory 分派:`config.platform` 決定後端類型(mock AdbClient,不起真進程)
  - `AdbDeviceBackend.capture`:mock `exec_out` 回固定 PNG bytes → 驗證 resize 到 (1080,1920)
- **config 測試**:`platform`/`adb_*` 欄位載入、預設值、`validate()`。

> 座標縮放與 `wm size`/`devices` 解析抽成純函數,無需 mock subprocess 即可單測。實機/模擬器端到端仍歸手動驗證(符合 CLAUDE.md「IO/GUI 層靠手動驗證」分層)。

## 範圍外 / 已知限制

- 真機黑邊/狀態列 letterbox 的座標修正(日後真機實測再補)。
- adb 設備掉線自動重連(本階段掉線即停)。
- 高效截圖後端(minicap/scrcpy)實作 —— 僅預留 `adb_screenshot_method` 介面。
- GUI 切換控件 —— 起步純 config,GUI 不動。
- ADB 模式下的多帳號/多設備並行 —— 單設備一次一個。

## 兼容性

- 舊 `config.json` 無 `platform` 欄位時預設 `"windows"`,行為與現版完全一致。
- `capture/`、`input/` 套件保留,Windows 後端程式碼不刪,僅由 `WindowsDeviceBackend` 組合呼叫。
- `img/` 模板、`constants.py`、matcher、ROI 設定完全不變,Windows 與 ADB 共用。
