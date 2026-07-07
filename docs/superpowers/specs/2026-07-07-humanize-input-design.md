# 輸入人性化(降低機器特徵)設計

**日期:** 2026-07-07
**狀態:** 已確認設計,待撰寫實施計劃
**平台:** Windows(SendInput)與 ADB 兩模式並行優化,各自發揮平台能力

**Goal:** 在不改動模板、ROI、matcher、constants、座標契約的前提下,為點擊/滑動注入隨機化的位置、軌跡與時序,降低自動化行為的機器特徵(固定節奏、勻速直線、瞬移點擊、恆定雙擊間隔),使刷商店行為更接近人類操作。

**Architecture:** 採分層方案——**節奏人性化歸 flow 層**(操作之間的停頓、抖動擴大),**輸入人性化歸 DeviceBackend 層**(位置抖動 + 平台軌跡),共用邏輯集中於新模組 `device/humanize.py`(純函數,可單元測試)。`click/swipe` 仍吃參考解析度座標、`capture()` 仍輸出 (1080,1920) BGR,flow 與 matcher 零改動。

**Tech Stack:** Python 3.9+、pywin32(SendInput/mouse_event)、adb、pytest。無新第三方依賴。

---

## 背景與目標

現有腳本的行為模式存在多處典型機器特徵,容易被行為分析識別:

| 面向 | 現況 | 機器特徵 |
|------|------|----------|
| 點擊時序 | `short_sleep` 抖動僅 `±0.2~0.3s`,各狀態用固定 multiplier(0.3/0.5/1.0/1.5) | 整體節奏可預測,連續掛機形成固定週期 |
| 點擊位置 | 永遠命中 `模板中心 + 固定 offset(800,40)` | 零偏差,人類點擊有像素級抖動 |
| 雙擊間隔 | 固定 `0.05s`(Win/ADB 皆然) | 完全一致,無變異 |
| 滑鼠軌跡(Win) | `SetCursorPos` 瞬移到目標後才 `down` | 無「游標接近」過程 |
| 滑動軌跡 | 10 步**勻速直線**插值 | 人類滑動是帶加減速的曲線 |
| 滑動起終點 | 固定 `(1400,500)→(1400,200)` | 每次完全相同 |
| 掛機節奏 | 事件驅動(圖像識別觸發)已相對自然 | 但無「偶爾停頓/看一下」機制 |

**正面基礎**:腳本已是事件驅動(圖像識別觸發點擊),非純定時腳本,本質上比定時自動化自然;ADB 的 `tap`/`swipe` 為系統級輸入,不像 Windows `mouse_event` 易被遊戲內 hook 識別來源,反檢測壓力較小。

## 已確認的決策(設計約束)

1. **優化面向**:聚焦「行為節奏太規律」+「點擊/滑動軌跡機械化」兩塊。**不做**「輸入事件來源偽裝」(如偽造 `dwExtraInfo`、驅動級注入)——那屬於更深度的反檢測工程,超出範圍。
2. **適用模式**:Windows 與 ADB 兩模式都要優化,在 `DeviceBackend` 介面統一抽象、各自實作平台能做的部分。
3. **效率取捨**:適度犧牲,整體刷商店耗時增加約 20~40%。
4. **架構**:方案 A 分層——節奏歸 flow、軌跡歸 device,共用純函數集中於 `device/humanize.py`。
5. **ADB 軌跡程度**:務實方案。ADB 只做**點擊位置抖動 + 滑動起終點抖動 + duration 隨機 + 雙擊間隔隨機**,滑動軌跡維持系統直線。**不做**逐點 `input motionevent` 曲線(每次滑動多 0.5~1s、adb 連線壓力大,超出「適度犧牲」)。理由:ADB 系統級輸入本身不易被識別來源,軌跡曲線的邊際效益不抵其開銷。
6. **後端解耦**:後端依賴輕量 `HumanizeSettings` dataclass,**不直接吃整份 `AppConfig`**。
7. **輸入後端注入**:`SendInputBackend` 於建構子接收 `HumanizeSettings`,方法簽名(`click/double_click/swipe`)**維持不變**,不破壞 `InputBackend` 抽象。
8. **總開關預設啟用**:`humanize_enabled` 預設 `true`。`false` 時**位元級退回現況**(跳過所有 jitter/軌跡/pause),作為 A/B 對照與問題排查的逃生通道。
9. **偶爾停頓位置**:`maybe_pause()` 置於主循環 `while should_continue:` 開頭,覆蓋所有狀態轉換。

## 核心問題:機器特徵的兩個來源

機器特徵來自兩個獨立層次,必須分別處理:

1. **單次輸入的幾何/時序特徵**(點擊零偏差、雙擊間隔恆定、滑動勻速直線、游標瞬移)——這是 `DeviceBackend`/`InputBackend` 的職責,與平台強相關。
2. **操作之間的節奏特徵**(每輪循環耗時一致、無停頓)——這是流程概念,歸屬 `flow`。

兩者若混在一層(例如把節奏停頓塞進 `click` 內部),會造成職責混亂、隨機化邏輯散落難調控。因此採分層:device 負責「單次輸入像人」,flow 負責「節奏像人」,共用隨機化原語集中於 `humanize.py`。

## 架構:分層 + 共用純函數(方案 A)

```
flow 層        →  節奏人性化(short_sleep 抖動擴大 + maybe_pause 偶爾停頓)
   │ 呼叫 device.click/swipe(參考解析度座標)
   ▼
DeviceBackend  →  輸入人性化(位置抖動 + 平台軌跡),各自實作
   │
   ├─ WindowsDeviceBackend → SendInputBackend:貝茲軌跡 + 加減速 + down-up 停留隨機
   └─ AdbDeviceBackend     → AdbClient:位置抖動 + 起終點抖動 + duration 隨機 + 雙擊間隔隨機
   ▲
device/humanize.py  →  共用純函數(兩後端 + flow 都呼叫),無 IO,可單元測試
```

選擇方案 A 而非「全部集中 device 層」(方案 B)或「最小改動不動軌跡」(方案 C)的理由:

- 方案 C 直接放棄軌跡優化,而軌跡機械化是已確認要解決的面向,不合格。
- 方案 B 把節奏停頓塞進 `click` 內部,語義混亂(「操作之間」的停頓不是單次 click 的職責),且兩後端重複隨機化邏輯。
- 方案 A 分工最清晰,共用純函數集中可測,符合專案既有「純函數 + dataclass」風格(如 `device/base.py`、`input/base.py` 的 `scale_to_client`)。

## 模組佈局

```
device/
  humanize.py       # 新建:純函數 + HumanizeSettings dataclass
  windows.py        # 修改:click/swipe 加位置抖動,注入 hs 給 SendInputBackend
  adb.py            # 修改:click/swipe/double_click 加抖動與時序隨機
input/
  sendinput.py      # 修改:click/swipe 改貝茲軌距+加減速,建構子收 hs
automation/
  flow.py           # 修改:short_sleep 抖動擴大 + 新增 maybe_pause() 於主循環開頭
config.py           # 修改:新增 humanize_* 欄位(全有預設值)
device/__init__.py  # 修改:create_device 組裝 HumanizeSettings 注入後端
```

| 檔案 | 動作 | 職責 |
|------|------|------|
| `device/humanize.py` | 新建 | 純函數(`jitter_point`、`jitter_swipe_endpoints`、`bezier_points`、`ease_in_out_weights`、`random_gap`、`roll`)+ `HumanizeSettings` dataclass |
| `input/sendinput.py` | 修改 | `__init__` 收 `hs`;`click`/`swipe` 改貝茲軌跡 + 加減速;`double_click` 間隔隨機;down-up 停留隨機 |
| `device/windows.py` | 修改 | `__init__` 收 `hs`;`click`/`swipe` 在參考座標空間先抖動再 `scale_to_client`;`SendInputBackend` 注入 `hs` |
| `device/adb.py` | 修改 | `__init__` 收 `hs`;`click` 抖動;`swipe` 起終點抖動 + duration 隨機;`double_click` 間隔隨機 |
| `device/__init__.py` | 修改 | `create_device` 從 `AppConfig` 組裝 `HumanizeSettings` 注入兩後端 |
| `automation/flow.py` | 修改 | `short_sleep` 抖動範圍擴大;新增 `maybe_pause()`;主循環開頭呼叫 |
| `config.py` | 修改 | 新增 `humanize_*` 欄位(全有預設值,舊 config 直接相容) |
| `tests/test_humanize.py` | 新建 | 6 個純函數單元測試 |
| `tests/test_config.py` | 修改 | 新欄位預設值、舊 config 載入相容 |
| `tests/test_flow.py` / `test_device.py` | 修改 | `enabled=False` 行為不變回歸;`enabled=True` 流程正常 |

**依賴方向**:`flow` → `device` → `device/humanize.py`;`input/sendinput` → `device/humanize.py`。

## `device/humanize.py`(純函數 + 設定)

```python
@dataclass
class HumanizeSettings:
    """後端唯一依賴的人性化設定,解耦 AppConfig。"""
    enabled: bool = True
    jitter_px: int = 8                 # 點擊抖動半徑(參考解析度 px)
    swipe_jitter_px: int = 20          # 滑動起終點抖動半徑
    double_click_gap: float = 0.05     # 雙擊間隔基準(固定,不暴露至 config)
    double_click_spread: float = 0.03  # 雙擊間隔抖動
    swipe_duration_spread: float = 0.04  # 滑動時長抖動(秒)
    curve_strength: float = 0.3        # 僅 Windows:貝茲控制點法向偏移比例
    move_steps: int = 12               # 僅 Windows:移動取樣點數
```

純函數(無 IO、無副作用,易單測):

| 函數 | 語義 | 實作要點 |
|------|------|----------|
| `jitter_point(x, y, r) -> (float, float)` | 在以 (x,y) 為中心、半徑 r 的圓內均勻取點 | `angle=U(0,2π)`、`rad=r*√U(0,1)`(√ 確保圓內均勻而非集中圓心);`r=0` 或 `enabled=False` 回原點 |
| `jitter_swipe_endpoints(p1, p2, r) -> ((x,y),(x,y))` | 起終點各自 `jitter_point` | r 通常大於點擊抖動 |
| `bezier_points(p0, p1, p2, p3, n) -> list[(x,y)]` | 三階貝茲曲線取 n 點 | `B(t)=(1-t)³P0+3(1-t)²t·P1+3(1-t)t²·P2+t³P3`,t=0..1 等分;`t=0→P0`、`t=1→P3` 端點精確 |
| `ease_in_out_weights(n) -> list[float]` | 加減速時間權重,總和=1 | `t_i=i/(n-1)`、`e_i=0.5(1-cos(π·t_i))`,權重=前後差分;先慢後快再慢 |
| `random_gap(base, spread) -> float` | `max(0.01, base + U(-spread, spread))` | 恆正值,eps 防退化 |
| `roll(chance) -> bool` | `U(0,1) < chance` | `chance≤0` 恆 `False`、`chance≥1` 恆 `True` |
| `roll_sign() -> int` | 隨機回傳 `+1` 或 `-1` | 等價 `1 if roll(0.5) else -1`;用於軌跡法向偏移隨機左右 |

> **座標空間**:這些函數與座標空間無關(吃什麼吐什麼)。Windows 後端在**螢幕座標**空間呼叫(貝茲軌跡);ADB 後端在**設備座標**空間呼叫(僅 jitter_point);抖動則統一在**參考解析度座標**空間做(後端收到 ref 座標後立即抖動,再縮放),與現有縮放流程無衝突。

## WindowsDeviceBackend + SendInputBackend(完整軌跡)

**位置抖動在 backend 層(參考座標空間),軌跡生成在 SendInputBackend(螢幕座標空間)。**

```python
# device/windows.py
class WindowsDeviceBackend(DeviceBackend):
    def __init__(self, hwnd, capture_method="auto", hs: HumanizeSettings = None):
        self._hwnd = hwnd
        self._capture_method = capture_method
        self._hs = hs or HumanizeSettings()
        self._input = SendInputBackend(self._hs)   # 注入 hs

    def click(self, ref_x, ref_y):
        if self._hs.enabled:
            ref_x, ref_y = humanize.jitter_point(ref_x, ref_y, self._hs.jitter_px)
        x, y = scale_to_client(self._hwnd, ref_x, ref_y)
        self._input.click(self._hwnd, x, y)        # 軌跡在 SendInputBackend 內生成

    def swipe(self, x1, y1, x2, y2, duration=0.1):
        if self._hs.enabled:
            (x1, y1), (x2, y2) = humanize.jitter_swipe_endpoints(
                (x1, y1), (x2, y2), self._hs.swipe_jitter_px)
        sx1, sy1 = scale_to_client(self._hwnd, x1, y1)
        sx2, sy2 = scale_to_client(self._hwnd, x2, y2)
        self._input.swipe(self._hwnd, sx1, sy1, sx2, sy2, duration)
```

```python
# input/sendinput.py —— click 改造
class SendInputBackend(InputBackend):
    def __init__(self, hs: HumanizeSettings = None):
        self._hs = hs or HumanizeSettings()

    def click(self, hwnd, x, y):
        sx, sy = win32gui.ClientToScreen(hwnd, (int(x), int(y)))
        if self._hs.enabled:
            self._move_along_bezier(sx, sy)        # 游標從當前位置貝茲移到目標
        else:
            win32api.SetCursorPos((sx, sy)); time.sleep(0.02)   # 退回現況
        win32api.mouse_event(MOUSEEVENTF_LEFTDOWN, sx, sy, 0, 0)
        time.sleep(humanize.random_gap(0.02, 0.015))           # down-up 停留隨機
        win32api.mouse_event(MOUSEEVENTF_LEFTUP, sx, sy, 0, 0)

    def double_click(self, hwnd, x, y):
        self.click(hwnd, x, y)
        time.sleep(humanize.random_gap(self._hs.double_click_gap,
                                       self._hs.double_click_spread))  # 取代固定 0.05
        self.click(hwnd, x, y)

    def _move_along_bezier(self, tx, ty):
        sx, sy = win32api.GetCursorPos()           # 當前游標(螢幕座標)為起點
        if (sx, sy) == (tx, ty):
            return
        dx, dy = tx - sx, ty - sy
        dist = (dx*dx + dy*dy) ** 0.5 or 1.0
        nx, ny = -dy / dist, dx / dist              # 連線法向量
        offset = dist * self._hs.curve_strength * humanize.roll_sign()  # 隨機左右偏
        # P0=起點, P1=1/3 處+偏移, P2=2/3 處+偏移, P3=目標
        p1 = (sx + dx/3 + nx*offset, sy + dy/3 + ny*offset)
        p2 = (sx + 2*dx/3 + nx*offset, sy + 2*dy/3 + ny*offset)
        pts = humanize.bezier_points((sx, sy), p1, p2, (tx, ty), self._hs.move_steps)
        weights = humanize.ease_in_out_weights(self._hs.move_steps)
        move_dur = humanize.random_gap(0.15, 0.08)  # 移動總時長
        for (px, py), w in zip(pts, weights):
            win32api.SetCursorPos((int(px), int(py)))
            time.sleep(w * move_dur)
```

`swipe` 同理:起終點抖動後(在 backend 層),以貝茲軌跡(4 控制點,法向偏移產生弧度)+ `ease_in_out_weights` 加減速,取代現有 10 步勻速直線。`_move_along_bezier` 與 `swipe` 共用 `bezier_points`/`ease_in_out_weights`。

> **`roll_sign()`**:`humanize` 提供回傳 `+1/-1` 的隨機符號小工具(等價 `1 if roll(0.5) else -1`),用於軌跡隨機左右偏。

## AdbDeviceBackend(務實方案)

ADB 受限於 adb 指令能力,不做逐點曲線。位置抖動 + 起終點抖動 + 時序隨機即足夠:

```python
class AdbDeviceBackend(DeviceBackend):
    def __init__(self, client, hs: HumanizeSettings = None):
        self._client = client
        self._hs = hs or HumanizeSettings()
        self._w, self._h = client.wm_size()

    def click(self, ref_x, ref_y):
        if self._hs.enabled:
            ref_x, ref_y = humanize.jitter_point(ref_x, ref_y, self._hs.jitter_px)
        dx, dy = scale_ref_to_device(ref_x, ref_y, self._w, self._h)
        self._client.tap(dx, dy)

    def double_click(self, ref_x, ref_y):
        self.click(ref_x, ref_y)
        time.sleep(humanize.random_gap(self._hs.double_click_gap,
                                       self._hs.double_click_spread))  # 取代固定 0.05
        self.click(ref_x, ref_y)

    def swipe(self, x1, y1, x2, y2, duration=0.1):
        if self._hs.enabled:
            (x1, y1), (x2, y2) = humanize.jitter_swipe_endpoints(
                (x1, y1), (x2, y2), self._hs.swipe_jitter_px)
            duration = humanize.random_gap(duration, self._hs.swipe_duration_spread)
        sx1, sy1 = scale_ref_to_device(x1, y1, self._w, self._h)
        sx2, sy2 = scale_ref_to_device(x2, y2, self._w, self._h)
        self._client.swipe(sx1, sy1, sx2, sy2, int(duration * 1000))  # 軌跡維持系統直線
```

> **為何 ADB 不做曲線**:`adb shell input swipe` 軌跡由 Android 系統生成(直線+系統插值),無法注入曲線。要曲線只能逐點 `adb shell input motionevent`(DOWN→多個MOVE→UP),每點一次子進程,10 點 ≈ 額外 0.5~1s 且 adb 連線壓力大,超出「適度犧牲」。ADB 系統級輸入本身不易被識別來源,務實方案性價比最高。

## flow 層節奏強化(`automation/flow.py`)

只動兩處,**不碰 `wait_for`/`wait_for_gone`/`wait_for_stable` 的輪詢 `interval`**(那是反應速度,非行為節奏):

1. **`short_sleep` 抖動擴大**:`uniform(-0.2, 0.3)` → `uniform(-0.3, 0.6)`(更大、更不對稱)。`humanize_enabled=False` 時退回原 `(-0.2, 0.3)`,保證位元級一致。

   ```python
   def short_sleep(self, multiplier=1.0):
       if self.config.humanize_enabled:
           jitter = random.uniform(-0.3, 0.6)
       else:
           jitter = random.uniform(-0.2, 0.3)   # 退回現況
       delay = self.config.short_sleep_base * multiplier + jitter
       time.sleep(max(0.0, delay))
   ```

2. **新增 `maybe_pause()`,主循環開頭呼叫**:

   ```python
   def maybe_pause(self):
       if not self.config.humanize_enabled:
           return
       if humanize.roll(self.config.humanize_pause_chance):
           time.sleep(humanize.random_gap(
               self.config.humanize_pause_duration,
               self.config.humanize_pause_spread))

   def run(self):
       self._init()
       while self.ctx.should_continue:
           self.maybe_pause()          # ← 主循環開頭,覆蓋所有狀態轉換
           state = self.ctx.state
           ...   # 原狀態分派不變
   ```

預設 `pause_chance=0.12`,平均每 ~8 輪停一次 `1.5±1.0s`,模擬人類「看一下再繼續」。

## 配置變更(`config.py` + `config.json`)

新增欄位,**全部有預設值,舊 config.json 直接相容**:

```python
# ---- 人性化(降低機器特徵)----
humanize_enabled: bool = True                  # 總開關;False = 位元級退回現況
humanize_jitter_px: int = 8                    # 點擊位置抖動半徑(參考解析度 px)
humanize_swipe_jitter_px: int = 20             # 滑動起終點抖動半徑
humanize_double_click_spread: float = 0.03     # 雙擊間隔抖動(base 固定 0.05)
humanize_swipe_duration_spread: float = 0.04   # 滑動時長隨機(秒)
humanize_curve_strength: float = 0.3           # 僅 Windows:貝茲弧度
humanize_move_steps: int = 12                  # 僅 Windows:游標移動取樣點數
humanize_pause_chance: float = 0.12            # 偶爾停頓機率
humanize_pause_duration: float = 1.5           # 停頓基準秒數
humanize_pause_spread: float = 1.0             # 停頓抖動秒數
```

- `double_click_gap`(0.05)固定不暴露,僅藏於 `HumanizeSettings` 預設。
- `validate()` 不對 `humanize_*` 做嚴格範圍校驗(數值語義寬鬆,異常值最壞只讓行為更隨機);僅在 `_coerce` 維持型別正確。
- `create_device(config)` 內以輔助函式組裝 `HumanizeSettings`:

  ```python
  def _humanize_settings(config: AppConfig) -> HumanizeSettings:
      return HumanizeSettings(
          enabled=config.humanize_enabled,
          jitter_px=config.humanize_jitter_px,
          swipe_jitter_px=config.humanize_swipe_jitter_px,
          double_click_gap=0.05,
          double_click_spread=config.humanize_double_click_spread,
          swipe_duration_spread=config.humanize_swipe_duration_spread,
          curve_strength=config.humanize_curve_strength,
          move_steps=config.humanize_move_steps,
      )
  ```

  注入:`WindowsDeviceBackend(hwnd, capture_method, hs)` / `AdbDeviceBackend(client, hs)`。

## 關鍵不變量

1. **`enabled=False` 位元級退回**:跳過所有 jitter/軌跡/pause,`short_sleep` 退回原抖動範圍。行為與改動前完全一致,作 A/B 對照與問題排查。
2. **座標契約不變**:`click/swipe` 仍吃參考解析度座標、`capture()` 仍輸出 (1080,1920) BGR。matcher、ROI、`constants.py`、模板零改動。
3. **後端介面不變**:`DeviceBackend.click/double_click/swipe` 簽名不變;`InputBackend` 方法簽名不變(hs 走建構子)。
4. **向後相容**:舊 `config.json` 無 `humanize_*` 欄位 → 用預設值(`enabled=True`)。使用者若要維持舊節奏,設 `humanize_enabled: false`。

## 錯誤處理 / 邊界

| 場景 | 處理 |
|------|------|
| jitter 後座標超出視窗 | 抖動半徑小(8px),實務不會出界;仍 clamp 到 `[0, REF_WIDTH/HEIGHT]` 防禦(在 backend 層 jitter 後) |
| Windows 貝茲起點 `GetCursorPos()` 在視窗外 | 無妨,軌跡自然將游標拉回目標,反而更像人 |
| ADB duration 過小被拒 | `random_gap` 恆 ≥ eps,避免退化為 tap |
| `move_steps` 過小(如 1) | `ease_in_out_weights`/`bezier_points` 對 n≤1 防禦(回退為直接 SetCursorPos) |
| `humanize_enabled=False` | 全分支跳過,行為位元級等同現況 |

## 測試策略

| 測試 | 對象 | 驗證 |
|------|------|------|
| `tests/test_humanize.py`(新建) | 7 純函數 | `jitter_point`:偏移在半徑內、`r=0` 回原點、中心正確;`bezier_points`:`t=0→P0`/`t=1→P3`、點數正確;`ease_in_out_weights`:總和≈1、單調遞增、首尾權重小;`random_gap`:恆 ≥ 0.01、落在 `[base-spread, base+spread]`;`roll`:`chance=0` 恆 `False`、`chance=1` 恆 `True`;`roll_sign`:只回傳 ±1;`jitter_swipe_endpoints`:兩端各自在半徑內 |
| `tests/test_config.py`(擴充) | `AppConfig` | 新欄位預設值正確;舊 `config.json`(無 `humanize_*`)載入不報錯、用預設;`_coerce` 型別正確 |
| `tests/test_flow.py`(回歸) | `FakeDevice` | `enabled=False`:`short_sleep` 抖動範圍、`maybe_pause` 不停頓、流程行為與改動前一致;`enabled=True`:流程仍正常完成、`FakeDevice` 收到點擊、`maybe_pause` 偶爾觸發 |
| `tests/test_device.py`(回歸) | 後端 + `FakeDevice` | `enabled=False`:`click/swipe` 座標不抖動(== 輸入值);`enabled=True`:`click` 座標在抖動半徑內、`swipe` 起終點偏移在範圍內 |
| 手動驗證 | Windows/ADB 真機 | IO/GUI 層靠手動(CLAUDE.md 既有方針):Windows 觀察游標軌跡成弧線、滑動加減速、雙擊間隔變化;ADB 觀察點擊位置每次略不同、滑動時長變化;兩模式刷商店完整流程正常 |

## 文件同步

- **`CLAUDE.md`**:模組職責表新增 `device/humanize.py`;Configuration 段補 `humanize_*` 欄位說明;「設備後端」段補註人性化分層。
- **`README.md`**:新增「人性化/降低機器特徵」段落,說明預設啟用、可調強度、`humanize_enabled: false` 關閉方式。

## 範圍外 / 已知限制

- **輸入事件來源偽裝**:不偽造 `dwExtraInfo`、不做驅動級/硬體級注入。Windows 仍用 `mouse_event`(SendInput 簡化封裝),事件來源特徵不變——本設計只降低「行為模式」特徵,不處理「事件來源」特徵。
- **ADB 滑動曲線軌跡**:務實方案維持系統直線,不做逐點 `motionevent` 曲線。
- **掛機時長/時段限制**:不做「連續 N 小時強制休息」「每日時段限制」等巨觀節奏控制(那是另一個獨立面向,如需可另立 spec)。
- **無意義動作**:不做「偶爾開背包、滑動商店頂部」等擬人小動作(YAGNI)。
- **多帳號行為模式多樣化**:單一設定套用所有運行,不為每次運行生成獨立隨機檔。

## 兼容性

- 舊 `config.json` 無 `humanize_*` 欄位 → 用預設值,`enabled=True` 自動啟用(行為變慢約 20~40%,文件註明可設 `false` 關閉)。
- `device/`、`input/`、`automation/` 介面簽名不變,`worker.py` 組裝流程不變(僅 `create_device` 內部多組裝 `HumanizeSettings`)。
- `img/` 模板、`constants.py`、matcher、ROI 設定完全不變。
- `enabled=False` 為位元級退回,可用於比對改動前後行為差異、排查「是不是人性化導致的問題」。
