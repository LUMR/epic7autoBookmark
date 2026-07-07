# 輸入人性化(降低機器特徤)實施計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 為點擊/滑動注入隨機化的位置、軌跡與時序,降低自動化行為的機器特徵(固定節奏、勻速直線、瞬移點擊、恆定雙擊間隔),使刷商店行為更接近人類操作。

**Architecture:** 分層方案——節奏人性化歸 flow 層(`short_sleep` 抖動擴大 + 主循環 `maybe_pause`),輸入人性化歸 DeviceBackend 層(位置抖動 + 平台軌跡),共用邏輯集中於新模組 `device/humanize.py`(純函數,可單元測試)。Windows 做貝茲軌跡 + 加減速;ADB 務實方案(位置/起終點抖動 + 時序隨機)。

**Tech Stack:** Python 3.9+、pywin32(SendInput/mouse_event)、adb 子進程、pytest。無新第三方依賴。

## Global Constraints

(摘自 spec `docs/superpowers/specs/2026-07-07-humanize-input-design.md`,每個任務隱含遵守)

- **座標契約不變**:`click/swipe` 吃參考解析度座標(1920×1080);`capture()` 恆輸出 BGR ndarray (1080,1920,3)。matcher、ROI、`constants.py`、模板零改動。
- **`DeviceBackend` / `InputBackend` 方法簽名不變**:人性化設定 `hs` 走**建構子**注入,不進入方法簽名。
- **後端解耦**:後端依賴 `device.humanize.HumanizeSettings`,**不直接吃整份 `AppConfig`**。
- **`humanize_enabled` 預設 `True`**;`False` 時**位元級退回現況**(跳過所有 jitter/軌跡/pause,`short_sleep` 退回 `uniform(-0.2, 0.3)`)。
- **向後相容**:舊 `config.json` 無 `humanize_*` 欄位 → 用預設值,不報錯。
- **程式碼風格**:中文註解(對齊 `device/adb.py`、`automation/flow.py` 既有風格);`from __future__ import annotations`。
- **提交不署名**(CLAUDE.md);commit message 用 conventional commits 中文。
- **後端建構子 `hs` 參數須有預設值** `hs: HumanizeSettings | None = None`(用 `or HumanizeSettings()` 補預設),確保 Task 5(factory 注入)就緒前既有測試不傳 `hs` 仍可運作。

---

## File Structure

| 檔案 | 動作 | 職責 |
|------|------|------|
| `device/humanize.py` | 新建 | 7 個純函數 + `HumanizeSettings` dataclass |
| `tests/test_humanize.py` | 新建 | 7 純函數單元測試 |
| `config.py` | 修改 | 新增 10 個 `humanize_*` 欄位 |
| `tests/test_config.py` | 修改 | 新欄位預設值 + 舊 config 相容 |
| `device/adb.py` | 修改 | 建構子收 `hs`;click/swipe/double_click 抖動 + 時序隨機 |
| `tests/test_device.py` | 修改 | `_adb_device` helper 傳 disabled `hs`;新增人性化行為測試 |
| `input/sendinput.py` | 修改 | 建構子收 `hs`;click/double_click/swipe 改貝茲軌跡 + 加減速 |
| `device/windows.py` | 修改 | 建構子收 `hs`;click/double_click/swipe 位置抖動 + 注入 `hs` 給 SendInputBackend |
| `tests/test_device.py` | 修改 | Windows 測試 patch 改 `lambda hs=None`;傳 disabled `hs`;新增抖動測試 |
| `device/__init__.py` | 修改 | `_humanize_settings(config)` 組裝 + `create_device` 注入 `hs` |
| `tests/test_device.py` | 修改 | factory 測試 patch 收 `hs`;新增 `_humanize_settings` 測試 |
| `automation/flow.py` | 修改 | `short_sleep` 抖動擴大 + 新增 `maybe_pause()` 於主循環開頭 |
| `tests/test_flow.py` | 修改 | `_mk_flow` 設 `humanize_enabled=False`;新增節奏測試 |
| `CLAUDE.md` | 修改 | 模組表加 `device/humanize.py`;Configuration 加 `humanize_*` |
| `README.md` | 修改 | 新增「人性化/降低機器特徵」段落 |

**依賴順序**:Task 1(humanize)→ Task 2(config)→ Task 3(adb)→ Task 4(windows)→ Task 5(factory)→ Task 6(flow)→ Task 7(docs)。Task 1 是所有裝置/流程任務的基礎。

---

## Task 1: `device/humanize.py` 純函數 + `HumanizeSettings`

**Files:**
- Create: `device/humanize.py`
- Test: `tests/test_humanize.py`

**Interfaces:**
- Produces: `HumanizeSettings` dataclass;純函數 `jitter_point(x, y, r) -> (float, float)`、`jitter_swipe_endpoints(p1, p2, r) -> ((x,y),(x,y))`、`clamp_ref(x, y) -> (float, float)`、`bezier_points(p0, p1, p2, p3, n) -> list[(x,y)]`、`ease_in_out_weights(n) -> list[float]`、`random_gap(base, spread) -> float`、`roll(chance) -> bool`、`roll_sign() -> int`。後續任務以此為唯一人性化 API。

- [ ] **Step 1: 寫失敗測試(完整 `tests/test_humanize.py`)**

```python
"""humanize 純函數單元測試。"""
import math

import pytest

from capture import REF_WIDTH, REF_HEIGHT
from device.humanize import (
    HumanizeSettings,
    jitter_point,
    jitter_swipe_endpoints,
    clamp_ref,
    bezier_points,
    ease_in_out_weights,
    random_gap,
    roll,
    roll_sign,
)


def test_humanize_settings_defaults():
    hs = HumanizeSettings()
    assert hs.enabled is True
    assert hs.jitter_px == 8
    assert hs.swipe_jitter_px == 20
    assert hs.double_click_gap == 0.05
    assert hs.double_click_spread == 0.03
    assert hs.swipe_duration_spread == 0.04
    assert hs.curve_strength == 0.3
    assert hs.move_steps == 12


def test_jitter_point_within_radius():
    for _ in range(200):
        jx, jy = jitter_point(100.0, 100.0, 8)
        dist = math.hypot(jx - 100.0, jy - 100.0)
        assert dist <= 8.0 + 1e-9


def test_jitter_point_zero_radius_returns_center():
    assert jitter_point(100.0, 100.0, 0) == (100.0, 100.0)
    assert jitter_point(100.0, 100.0, -3) == (100.0, 100.0)


def test_jitter_swipe_endpoints_both_within_radius():
    (a1, a2), (b1, b2) = jitter_swipe_endpoints((0.0, 0.0), (100.0, 100.0), 5)
    assert math.hypot(a1, a2) <= 5.0 + 1e-9
    assert math.hypot(b1 - 100.0, b2 - 100.0) <= 5.0 + 1e-9


def test_clamp_ref_within_bounds_unchanged():
    assert clamp_ref(100.0, 200.0) == (100.0, 200.0)


def test_clamp_ref_clamps_out_of_bounds():
    assert clamp_ref(-5.0, 5000.0) == (0.0, float(REF_HEIGHT))
    assert clamp_ref(5000.0, -5.0) == (float(REF_WIDTH), 0.0)


def test_bezier_points_count_and_endpoints():
    pts = bezier_points((0.0, 0.0), (1.0, 2.0), (3.0, 4.0), (5.0, 0.0), 10)
    assert len(pts) == 10
    assert pts[0] == pytest.approx((0.0, 0.0))   # t=0 -> P0
    assert pts[-1] == pytest.approx((5.0, 0.0))  # t=1 -> P3


def test_bezier_points_n_less_than_two():
    assert bezier_points((1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (4.0, 4.0), 1) == [(1.0, 1.0)]
    assert bezier_points((1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (4.0, 4.0), 0) == [(1.0, 1.0)]


def test_ease_in_out_weights_count_and_sum():
    weights = ease_in_out_weights(12)
    assert len(weights) == 11            # n 點 -> n-1 段
    assert sum(weights) == pytest.approx(1.0)


def test_ease_in_out_weights_shape():
    """加減速:首尾段權重 < 中間段權重。"""
    weights = ease_in_out_weights(12)
    mid = len(weights) // 2
    assert weights[0] < weights[mid]
    assert weights[-1] < weights[mid]


def test_ease_in_out_weights_n_less_than_two():
    assert ease_in_out_weights(1) == []
    assert ease_in_out_weights(0) == []


def test_random_gap_always_positive_and_in_range():
    for _ in range(200):
        g = random_gap(0.05, 0.03)
        assert g >= 0.01
        assert 0.05 - 0.03 - 1e-9 <= g <= 0.05 + 0.03 + 1e-9


def test_roll_chance_zero_always_false():
    assert all(roll(0.0) is False for _ in range(100))


def test_roll_chance_one_always_true():
    assert all(roll(1.0) is True for _ in range(100))


def test_roll_sign_only_plus_minus_one():
    for _ in range(100):
        assert roll_sign() in (1, -1)
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `pytest tests/test_humanize.py -v`
Expected: FAIL(`ModuleNotFoundError: No module named 'device.humanize'`)

- [ ] **Step 3: 實作 `device/humanize.py`**

```python
"""輸入人性化純函數 + 設定 — 降低點擊/滑動的機器特徵。

所有函數無 IO、無副作用,可單元測試。座標空間由呼叫端決定
(參考解析度/螢幕/設備),函數本身與座標空間無關。
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from capture import REF_WIDTH, REF_HEIGHT


@dataclass
class HumanizeSettings:
    """後端唯一依賴的人性化設定,解耦 AppConfig。

    factory(device/__init__.py)從 AppConfig 扁平欄位組裝此物件注入後端;
    後端不直接依賴整份 AppConfig。
    """
    enabled: bool = True
    jitter_px: int = 8                  # 點擊抖動半徑(參考解析度 px)
    swipe_jitter_px: int = 20           # 滑動起終點抖動半徑
    double_click_gap: float = 0.05      # 雙擊間隔基準(固定,不暴露至 config)
    double_click_spread: float = 0.03   # 雙擊間隔抖動
    swipe_duration_spread: float = 0.04  # 滑動時長抖動(秒)
    curve_strength: float = 0.3         # 僅 Windows:貝茲控制點法向偏移比例
    move_steps: int = 12                # 僅 Windows:移動取樣點數


def jitter_point(x: float, y: float, r: float) -> tuple[float, float]:
    """在以 (x,y) 為中心、半徑 r 的圓內均勻取點。r<=0 回原點。

    用 sqrt(uniform) 確保圓內均勻分布(否則會集中圓心)。
    """
    if r <= 0:
        return float(x), float(y)
    angle = random.uniform(0, 2 * math.pi)
    radius = r * math.sqrt(random.uniform(0, 1))
    return x + radius * math.cos(angle), y + radius * math.sin(angle)


def jitter_swipe_endpoints(
    p1: tuple[float, float], p2: tuple[float, float], r: float
) -> tuple[tuple[float, float], tuple[float, float]]:
    """滑動起終點各自 jitter_point。"""
    return jitter_point(*p1, r), jitter_point(*p2, r)


def clamp_ref(x: float, y: float) -> tuple[float, float]:
    """將參考解析度座標 clamp 到 [0, REF_WIDTH]×[0, REF_HEIGHT](防禦抖動出界)。"""
    return (max(0.0, min(float(REF_WIDTH), x)), max(0.0, min(float(REF_HEIGHT), y)))


def bezier_points(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    n: int,
) -> list[tuple[float, float]]:
    """三階貝茲曲線取 n 點(含端點 t=0..1)。n<2 回 [p0]。

    B(t) = (1-t)^3 P0 + 3(1-t)^2 t P1 + 3(1-t) t^2 P2 + t^3 P3
    """
    if n < 2:
        return [(float(p0[0]), float(p0[1]))]
    pts: list[tuple[float, float]] = []
    for i in range(n):
        t = i / (n - 1)
        u = 1 - t
        a = u * u * u
        b = 3 * u * u * t
        c = 3 * u * t * t
        d = t * t * t
        x = a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0]
        y = a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]
        pts.append((x, y))
    return pts


def ease_in_out_weights(n: int) -> list[float]:
    """n 個取樣點之間的 n-1 段加減速權重(先慢後快再慢),總和=1。n<2 回 []。

    eased(t) = 0.5(1 - cos(πt)),t=0..1;權重 = 相鄰 eased 差分。
    """
    if n < 2:
        return []
    eased = [0.5 * (1 - math.cos(math.pi * i / (n - 1))) for i in range(n)]
    weights = [eased[i + 1] - eased[i] for i in range(n - 1)]
    total = sum(weights)
    if total <= 0:
        return [1.0 / (n - 1)] * (n - 1)
    return [w / total for w in weights]


def random_gap(base: float, spread: float) -> float:
    """base ± spread 的隨機間隔,恆 >= 0.01(防退化為零/負)。"""
    return max(0.01, base + random.uniform(-spread, spread))


def roll(chance: float) -> bool:
    """以機率 chance 回 True。chance<=0 恆 False,chance>=1 恆 True。"""
    return random.uniform(0, 1) < chance


def roll_sign() -> int:
    """隨機回 +1 或 -1(軌跡法向偏移隨機左右)。"""
    return 1 if roll(0.5) else -1
```

- [ ] **Step 4: 跑測試確認通過**

Run: `pytest tests/test_humanize.py -v`
Expected: 13 個測試 PASS

- [ ] **Step 5: 提交**

```bash
git add device/humanize.py tests/test_humanize.py
git commit -m "feat(humanize): 新增人性化純函數 + HumanizeSettings"
```

---

## Task 2: `config.py` 新增 `humanize_*` 欄位

**Files:**
- Modify: `config.py`(在「時序參數」段之後新增「人性化」段)
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: 無
- Produces: `AppConfig` 新欄位 `humanize_enabled`、`humanize_jitter_px`、`humanize_swipe_jitter_px`、`humanize_double_click_spread`、`humanize_swipe_duration_spread`、`humanize_curve_strength`、`humanize_move_steps`、`humanize_pause_chance`、`humanize_pause_duration`、`humanize_pause_spread`。Task 5 的 `_humanize_settings` 與 Task 6 的 flow 會讀這些。

- [ ] **Step 1: 寫失敗測試(附加至 `tests/test_config.py` 末尾)**

```python
def test_humanize_defaults():
    cfg = AppConfig._from_dict({})
    assert cfg.humanize_enabled is True
    assert cfg.humanize_jitter_px == 8
    assert cfg.humanize_swipe_jitter_px == 20
    assert cfg.humanize_double_click_spread == 0.03
    assert cfg.humanize_swipe_duration_spread == 0.04
    assert cfg.humanize_curve_strength == 0.3
    assert cfg.humanize_move_steps == 12
    assert cfg.humanize_pause_chance == 0.12
    assert cfg.humanize_pause_duration == 1.5
    assert cfg.humanize_pause_spread == 1.0


def test_humanize_from_dict():
    raw = {
        "humanize_enabled": False,
        "humanize_jitter_px": 15,
        "humanize_pause_chance": 0.25,
    }
    cfg = AppConfig._from_dict(raw)
    assert cfg.humanize_enabled is False
    assert cfg.humanize_jitter_px == 15
    assert cfg.humanize_pause_chance == 0.25


def test_old_config_without_humanize_uses_defaults():
    """舊 config.json(無 humanize_*)載入用預設值,不報錯。"""
    raw = {"e7_language": "zh-TW", "default_money": 1000}
    cfg = AppConfig._from_dict(raw)
    assert cfg.humanize_enabled is True
    assert cfg.humanize_jitter_px == 8
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `pytest tests/test_config.py::test_humanize_defaults -v`
Expected: FAIL(`AttributeError: 'AppConfig' object has no attribute 'humanize_enabled'`)

- [ ] **Step 3: 修改 `config.py` — 在「時序參數」段之後(第 59 行 `swipe_fail_limit: int = 5` 之後)新增欄位**

找到:
```python
    # ---- 时序参数 ----
    short_sleep_base: float = 1.0
    wait_timeout: float = 5.0
    wait_timeout_long: float = 8.0
    max_retry: int = 20
    swipe_fail_limit: int = 5
```

在其後新增:
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

- [ ] **Step 4: 跑測試確認通過**

Run: `pytest tests/test_config.py -v`
Expected: 全部 PASS(含新增 3 個 + 既有)

- [ ] **Step 5: 提交**

```bash
git add config.py tests/test_config.py
git commit -m "feat(config): 新增 humanize_* 人性化設定欄位"
```

---

## Task 3: `AdbDeviceBackend` 務實人性化

**Files:**
- Modify: `device/adb.py`
- Test: `tests/test_device.py`

**Interfaces:**
- Consumes: `device.humanize`(Task 1):`HumanizeSettings`、`jitter_point`、`jitter_swipe_endpoints`、`random_gap`。
- Produces: `AdbDeviceBackend.__init__(client, hs=None)`;`click`/`swipe`/`double_click` 在 `enabled` 時注入抖動與時序隨機。Task 5 factory 會傳 `hs`。

- [ ] **Step 1: 寫失敗測試(附加至 `tests/test_device.py`)**

先在 `tests/test_device.py` 匯入區新增(`from device.adb import AdbDeviceBackend` 已存在,只需補 humanize):
```python
from device.humanize import HumanizeSettings
```

附加測試函式:
```python
def test_adb_device_click_jitters_when_enabled(monkeypatch):
    """enabled 時 tap 座標偏移在 jitter_px 縮放範圍內(非精確 640,360)。"""
    client = MagicMock()
    client.wm_size.return_value = parse_wm_size("Physical size: 1280x720")
    dev = AdbDeviceBackend(client, hs=HumanizeSettings(enabled=True, jitter_px=8))
    dev.click(960, 540)  # 960,540 縮放到 1280x720 = 640,360
    tx, ty = client.tap.call_args[0]
    # 縮放後精確值 640,360;抖動 8px(ref) → device 座標偏移 <= 8*1280/1920
    assert math.isclose(tx, 640, abs_tol=8)
    assert math.isclose(ty, 360, abs_tol=8)
    assert (tx, ty) != (640, 360) or True  # 抖動可能恰好不變,僅驗範圍


def test_adb_device_swipe_jitters_endpoints_and_duration(monkeypatch):
    """enabled 時 swipe 座標與 duration 都被隨機化。"""
    client = MagicMock()
    client.wm_size.return_value = parse_wm_size("Physical size: 1920x1080")
    dev = AdbDeviceBackend(
        client, hs=HumanizeSettings(enabled=True, swipe_jitter_px=10, swipe_duration_spread=0.1)
    )
    dev.swipe(100, 200, 100, 800, duration=0.3)
    args = client.swipe.call_args[0]
    sx1, sy1, sx2, sy2, ms = args
    # 座標偏移在 10px 內,duration 偏移在 0.1s(=100ms)內
    assert math.isclose(sx1, 100, abs_tol=10)
    assert math.isclose(sy2, 800, abs_tol=10)
    assert math.isclose(ms, 300, abs_tol=100)


def test_adb_device_double_click_random_gap(monkeypatch):
    """double_click 兩次 tap 之間使用隨機間隔(固定 0.05 之外的值)。"""
    client = MagicMock()
    client.wm_size.return_value = parse_wm_size("Physical size: 1920x1080")
    dev = AdbDeviceBackend(client, hs=HumanizeSettings(enabled=True))
    sleeps = []
    monkeypatch.setattr("device.adb.time.sleep", lambda s: sleeps.append(s))
    dev.double_click(960, 540)
    assert client.tap.call_count == 2
    # 兩 tap 之間應有一次 sleep(double_click 間隔),值在 [0.02, 0.08]
    between = [s for s in sleeps if 0.02 <= s <= 0.08]
    assert len(between) >= 1
```

別忘了在 `tests/test_device.py` 頂部加 `import math`(若尚未匯入)。

- [ ] **Step 2: 跑測試確認失敗**

Run: `pytest tests/test_device.py::test_adb_device_click_jitters_when_enabled -v`
Expected: FAIL(`AdbDeviceBackend.__init__() got an unexpected keyword argument 'hs'`)

- [ ] **Step 3: 修改 `device/adb.py` — 建構子收 `hs` + 三個方法注入人性化**

完整替換 `device/adb.py` 內容為:
```python
"""AdbDeviceBackend — 以 adb 指令截圖/輸入的設備後端。"""

from __future__ import annotations

import time

import cv2
import numpy as np

from capture import REF_WIDTH, REF_HEIGHT
from device.adb_client import AdbClient
from device.base import DeviceBackend, DeviceError, scale_ref_to_device
from device.humanize import HumanizeSettings, jitter_point, jitter_swipe_endpoints, clamp_ref, random_gap


class AdbDeviceBackend(DeviceBackend):
    def __init__(self, client: AdbClient, hs: HumanizeSettings | None = None):
        self._client = client
        self._hs = hs or HumanizeSettings()
        self._w, self._h = client.wm_size()        # 啟動偵測一次,快取
        if self._w <= 0 or self._h <= 0:
            raise DeviceError(f"無效的設備解析度: {self._w}x{self._h}")

    def capture(self) -> np.ndarray:
        png = self._client.exec_out(["screencap", "-p"])
        try:
            img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
        except cv2.error:
            raise DeviceError("adb screencap 解碼失敗")
        if img is None:
            raise DeviceError("adb screencap 解碼失敗")
        if (self._w, self._h) != (REF_WIDTH, REF_HEIGHT):
            img = cv2.resize(img, (REF_WIDTH, REF_HEIGHT))
        return img

    def click(self, ref_x: float, ref_y: float) -> None:
        if self._hs.enabled:
            ref_x, ref_y = jitter_point(ref_x, ref_y, self._hs.jitter_px)
            ref_x, ref_y = clamp_ref(ref_x, ref_y)
        dx, dy = scale_ref_to_device(ref_x, ref_y, self._w, self._h)
        self._client.tap(dx, dy)

    def double_click(self, ref_x: float, ref_y: float) -> None:
        # adb 無原生雙擊 → 兩次 tap,間隔隨機化(取代固定 0.05)
        self.click(ref_x, ref_y)
        time.sleep(random_gap(self._hs.double_click_gap, self._hs.double_click_spread))
        self.click(ref_x, ref_y)

    def swipe(
        self, x1: float, y1: float, x2: float, y2: float, duration: float = 0.1
    ) -> None:
        if self._hs.enabled:
            (x1, y1), (x2, y2) = jitter_swipe_endpoints(
                (x1, y1), (x2, y2), self._hs.swipe_jitter_px)
            x1, y1 = clamp_ref(x1, y1)
            x2, y2 = clamp_ref(x2, y2)
            duration = random_gap(duration, self._hs.swipe_duration_spread)
        sx1, sy1 = scale_ref_to_device(x1, y1, self._w, self._h)
        sx2, sy2 = scale_ref_to_device(x2, y2, self._w, self._h)
        self._client.swipe(sx1, sy1, sx2, sy2, int(duration * 1000))

    @property
    def resolution(self) -> tuple[int, int]:
        return self._w, self._h
```

- [ ] **Step 4: 更新既有精確座標測試 — `_adb_device` helper 傳 disabled `hs`**

既有測試(`test_adb_device_click_scales`、`test_adb_device_swipe_converts_duration_to_ms`、`test_adb_device_double_click_two_taps` 等)斷言精確座標,但 `enabled` 預設 True 會抖動破壞它們。讓 helper 預設用 disabled `hs`。

找到 `tests/test_device.py` 中的:
```python
def _adb_device(monkeypatch, wm="Physical size: 1280x720"):
    client = MagicMock()
    client.wm_size.return_value = parse_wm_size(wm)
    return AdbDeviceBackend(client), client
```

替換為:
```python
def _adb_device(monkeypatch, wm="Physical size: 1280x720", hs=None):
    client = MagicMock()
    client.wm_size.return_value = parse_wm_size(wm)
    # 預設 disabled:既有精確座標測試驗證縮放邏輯,不受人性化影響
    return AdbDeviceBackend(client, hs=hs or HumanizeSettings(enabled=False)), client
```

- [ ] **Step 5: 跑全部 device 測試確認通過**

Run: `pytest tests/test_device.py -v`
Expected: 全部 PASS(既有精確測試因 disabled 維持精確 + 3 個新人性化測試)

- [ ] **Step 6: 提交**

```bash
git add device/adb.py tests/test_device.py
git commit -m "feat(adb): 點擊/滑動/雙擊務實人性化(抖動+時序隨機)"
```

---

## Task 4: `SendInputBackend` + `WindowsDeviceBackend` 貝茲軌跡與位置抖動

**Files:**
- Modify: `input/sendinput.py`、`device/windows.py`
- Test: `tests/test_device.py`

**Interfaces:**
- Consumes: `device.humanize`(Task 1):`HumanizeSettings`、`bezier_points`、`ease_in_out_weights`、`random_gap`、`roll_sign`。
- Produces: `SendInputBackend.__init__(hs=None)`(內部生成貝茲軌跡);`WindowsDeviceBackend.__init__(hwnd, capture_method="auto", hs=None)`(位置抖動 + 注入 `hs` 給 SendInputBackend)。Task 5 factory 會傳 `hs`。

- [ ] **Step 1: 寫失敗測試(附加至 `tests/test_device.py`)**

附加測試函式(`math` 已在 Task 3 匯入):
```python
def test_windows_device_click_jitters_when_enabled(monkeypatch):
    """enabled 時傳給 input 的座標在 jitter 範圍內(非精確縮放值)。"""
    monkeypatch.setattr("device.windows.scale_to_client", lambda hwnd, x, y: (x, y))
    fake_input = MagicMock()
    monkeypatch.setattr("device.windows.SendInputBackend", lambda hs=None: fake_input)
    dev = WindowsDeviceBackend(
        hwnd=42, capture_method="bitblt", hs=HumanizeSettings(enabled=True, jitter_px=8)
    )
    dev.click(1000, 500)
    args = fake_input.click.call_args[0]
    # scale_to_client 為恆等,故抖動後座標偏移在 8px 內
    assert math.isclose(args[1], 1000, abs_tol=8)
    assert math.isclose(args[2], 500, abs_tol=8)


def test_windows_device_swipe_jitters_endpoints(monkeypatch):
    monkeypatch.setattr("device.windows.scale_to_client", lambda hwnd, x, y: (x, y))
    fake_input = MagicMock()
    monkeypatch.setattr("device.windows.SendInputBackend", lambda hs=None: fake_input)
    dev = WindowsDeviceBackend(
        hwnd=42, capture_method="bitblt", hs=HumanizeSettings(enabled=True, swipe_jitter_px=10)
    )
    dev.swipe(100, 200, 100, 800, duration=0.3)
    args = fake_input.swipe.call_args[0]
    assert math.isclose(args[1], 100, abs_tol=10)
    assert math.isclose(args[4], 800, abs_tol=10)


def test_sendinput_click_moves_cursor_when_enabled(monkeypatch):
    """enabled 時 click 沿軌跡多次 SetCursorPos;disabled 時瞬移一次。"""
    import input.sendinput as si
    setpos = MagicMock()
    down = up = MagicMock()
    monkeypatch.setattr(si.win32gui, "ClientToScreen", lambda hwnd, p: p)
    monkeypatch.setattr(si.win32api, "GetCursorPos", lambda: (0, 0))
    monkeypatch.setattr(si.win32api, "SetCursorPos", setpos)
    monkeypatch.setattr(si.win32api, "mouse_event", lambda *a: None)
    monkeypatch.setattr(si.time, "sleep", lambda s: None)

    backend = si.SendInputBackend(hs=HumanizeSettings(enabled=True, move_steps=12))
    backend.click(hwnd=1, x=500, y=500)
    # 軌跡應產生多個 SetCursorPos(move_steps-1 段),遠大於 disabled 的 1 次
    assert setpos.call_count >= 5

    setpos.reset_mock()
    backend_off = si.SendInputBackend(hs=HumanizeSettings(enabled=False))
    backend_off.click(hwnd=1, x=500, y=500)
    assert setpos.call_count == 1   # disabled:單次瞬移
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `pytest tests/test_device.py::test_windows_device_click_jitters_when_enabled -v`
Expected: FAIL(`WindowsDeviceBackend.__init__() got an unexpected keyword argument 'hs'`)

- [ ] **Step 3: 實作 `input/sendinput.py` — 建構子收 `hs` + 貝茲軌跡**

完整替換 `input/sendinput.py` 內容為:
```python
"""SendInput 輸入後端 — 使用 Win32 SendInput API 发送鼠标事件。

Epic Seven (Unity/OpenGL) 不响应 PostMessage 鼠标消息,因此只能使用系统级输入。
人性化啟用時:click 沿貝茲曲線移動游標 + 加減速;swipe 沿貝茲軌跡拖曳;
down-up 停留與雙擊間隔隨機化。
"""

from __future__ import annotations

import time

import win32api
import win32con
import win32gui

from device.humanize import (
    HumanizeSettings,
    bezier_points,
    ease_in_out_weights,
    random_gap,
    roll_sign,
)
from input.base import InputBackend


class SendInputBackend(InputBackend):
    """透過 SendInput API 發送滑鼠事件的輸入後端。"""

    def __init__(self, hs: HumanizeSettings | None = None):
        self._hs = hs or HumanizeSettings()

    def click(self, hwnd: int, x: float, y: float) -> None:
        sx, sy = win32gui.ClientToScreen(hwnd, (int(x), int(y)))
        if self._hs.enabled:
            self._move_along_bezier(sx, sy)
        else:
            win32api.SetCursorPos((sx, sy))
            time.sleep(0.02)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, sx, sy, 0, 0)
        time.sleep(random_gap(0.02, 0.015))  # down-up 停留隨機
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, sx, sy, 0, 0)

    def double_click(self, hwnd: int, x: float, y: float) -> None:
        self.click(hwnd, x, y)
        time.sleep(random_gap(self._hs.double_click_gap, self._hs.double_click_spread))
        self.click(hwnd, x, y)

    def swipe(
        self,
        hwnd: int,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        duration: float = 0.1,
    ) -> None:
        sx1, sy1 = win32gui.ClientToScreen(hwnd, (int(x1), int(y1)))
        sx2, sy2 = win32gui.ClientToScreen(hwnd, (int(x2), int(y2)))
        if self._hs.enabled:
            self._drag_along_bezier(sx1, sy1, sx2, sy2, duration)
            return
        # disabled:原勻速直線(位元級退回)
        win32api.SetCursorPos((sx1, sy1))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, sx1, sy1, 0, 0)
        steps = 10
        step_delay = duration / steps
        for i in range(1, steps + 1):
            t = i / steps
            cx = int(sx1 + (sx2 - sx1) * t)
            cy = int(sy1 + (sy2 - sy1) * t)
            win32api.SetCursorPos((cx, cy))
            time.sleep(step_delay)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, sx2, sy2, 0, 0)

    # ---- 內部:貝茲軌跡生成(螢幕座標空間)----

    def _bezier_control_points(self, sx, sy, tx, ty):
        """起終點 + 法向偏移的控制點。回傳 (p0, p1, p2, p3)。"""
        dx, dy = tx - sx, ty - sy
        dist = (dx * dx + dy * dy) ** 0.5 or 1.0
        nx, ny = -dy / dist, dx / dist            # 連線法向量
        off = dist * self._hs.curve_strength * roll_sign()
        p0 = (sx, sy)
        p1 = (sx + dx / 3 + nx * off, sy + dy / 3 + ny * off)
        p2 = (sx + 2 * dx / 3 + nx * off, sy + 2 * dy / 3 + ny * off)
        p3 = (tx, ty)
        return p0, p1, p2, p3

    def _move_along_bezier(self, tx, ty) -> None:
        """游標從當前位置沿貝茲曲線(加減速)移到目標。"""
        sx, sy = win32api.GetCursorPos()
        if (sx, sy) == (tx, ty):
            return
        p0, p1, p2, p3 = self._bezier_control_points(sx, sy, tx, ty)
        pts = bezier_points(p0, p1, p2, p3, self._hs.move_steps)
        weights = ease_in_out_weights(self._hs.move_steps)
        move_dur = random_gap(0.15, 0.08)
        for i in range(len(weights)):
            px, py = pts[i + 1]
            win32api.SetCursorPos((int(px), int(py)))
            time.sleep(weights[i] * move_dur)

    def _drag_along_bezier(self, sx1, sy1, sx2, sy2, duration) -> None:
        """按住左鍵沿貝茲軌跡(加減速)拖曳。"""
        p0, p1, p2, p3 = self._bezier_control_points(sx1, sy1, sx2, sy2)
        pts = bezier_points(p0, p1, p2, p3, self._hs.move_steps)
        weights = ease_in_out_weights(self._hs.move_steps)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, sx1, sy1, 0, 0)
        for i in range(len(weights)):
            px, py = pts[i + 1]
            win32api.SetCursorPos((int(px), int(py)))
            time.sleep(weights[i] * duration)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, sx2, sy2, 0, 0)
```

- [ ] **Step 4: 實作 `device/windows.py` — 建構子收 `hs` + 位置抖動 + 注入**

完整替換 `device/windows.py` 中 `WindowsDeviceBackend` 類別(保留 `find_game_window` 與 imports 區段,僅改 import 行與類別)。

找到 import 區段:
```python
from capture import capture_window
from capture.bitblt import close_all
from device.base import DeviceBackend
from input.base import scale_to_client
from input.sendinput import SendInputBackend
```

替換為:
```python
from capture import capture_window
from capture.bitblt import close_all
from device.base import DeviceBackend
from device.humanize import HumanizeSettings, jitter_point, jitter_swipe_endpoints, clamp_ref
from input.base import scale_to_client
from input.sendinput import SendInputBackend
```

找到 `WindowsDeviceBackend` 類別(從 `class WindowsDeviceBackend(DeviceBackend):` 到檔尾 `return rect[2], rect[3]`),替換為:
```python
class WindowsDeviceBackend(DeviceBackend):
    def __init__(self, hwnd: int, capture_method: str = "auto", hs: HumanizeSettings | None = None):
        self._hwnd = hwnd
        self._capture_method = capture_method
        self._hs = hs or HumanizeSettings()
        self._input = SendInputBackend(self._hs)

    def capture(self) -> np.ndarray:
        return capture_window(self._hwnd, self._capture_method)

    def click(self, ref_x: float, ref_y: float) -> None:
        if self._hs.enabled:
            ref_x, ref_y = jitter_point(ref_x, ref_y, self._hs.jitter_px)
            ref_x, ref_y = clamp_ref(ref_x, ref_y)
        x, y = scale_to_client(self._hwnd, ref_x, ref_y)
        self._input.click(self._hwnd, x, y)

    def double_click(self, ref_x: float, ref_y: float) -> None:
        if self._hs.enabled:
            ref_x, ref_y = jitter_point(ref_x, ref_y, self._hs.jitter_px)
            ref_x, ref_y = clamp_ref(ref_x, ref_y)
        x, y = scale_to_client(self._hwnd, ref_x, ref_y)
        self._input.double_click(self._hwnd, x, y)

    def swipe(
        self, x1: float, y1: float, x2: float, y2: float, duration: float = 0.1
    ) -> None:
        if self._hs.enabled:
            (x1, y1), (x2, y2) = jitter_swipe_endpoints(
                (x1, y1), (x2, y2), self._hs.swipe_jitter_px)
            x1, y1 = clamp_ref(x1, y1)
            x2, y2 = clamp_ref(x2, y2)
        sx1, sy1 = scale_to_client(self._hwnd, x1, y1)
        sx2, sy2 = scale_to_client(self._hwnd, x2, y2)
        self._input.swipe(self._hwnd, sx1, sy1, sx2, sy2, duration)

    def prepare(self) -> None:
        try:
            win32gui.SetForegroundWindow(self._hwnd)
        except Exception:
            pass  # 視窗可能已在前台

    def close(self) -> None:
        close_all()

    @property
    def resolution(self) -> tuple[int, int]:
        rect = win32gui.GetClientRect(self._hwnd)
        return rect[2], rect[3]
```

- [ ] **Step 5: 更新既有 Windows 測試 — patch 收 `hs` + 傳 disabled `hs`**

既有 4 個 windows 測試(`test_windows_device_click_delegates`、`test_windows_device_capture_delegates`、`test_windows_device_close_calls_close_all`、`test_windows_device_swipe_delegates`)的 patch `lambda: fake_input` 不收參數,但現在 `WindowsDeviceBackend` 呼叫 `SendInputBackend(self._hs)` 會帶一個參數;且 `enabled` 預設 True 會抖動破壞精確座標斷言。

逐一修正:

`test_windows_device_click_delegates` 找到:
```python
    monkeypatch.setattr("device.windows.scale_to_client", lambda hwnd, x, y: (x * 2, y * 2))
    fake_input = MagicMock()
    monkeypatch.setattr("device.windows.SendInputBackend", lambda: fake_input)

    dev = WindowsDeviceBackend(hwnd=42, capture_method="bitblt")
    dev.double_click(100, 50)
```
替換為:
```python
    monkeypatch.setattr("device.windows.scale_to_client", lambda hwnd, x, y: (x * 2, y * 2))
    fake_input = MagicMock()
    monkeypatch.setattr("device.windows.SendInputBackend", lambda hs=None: fake_input)

    dev = WindowsDeviceBackend(hwnd=42, capture_method="bitblt", hs=HumanizeSettings(enabled=False))
    dev.double_click(100, 50)
```

`test_windows_device_capture_delegates` 找到 `monkeypatch.setattr("device.windows.SendInputBackend", lambda: MagicMock())`,替換為 `lambda hs=None: MagicMock()`。

`test_windows_device_close_calls_close_all` 同樣把 `lambda: MagicMock()` 改 `lambda hs=None: MagicMock()`;建構 `WindowsDeviceBackend(hwnd=1)` 不變(此測試不涉及點擊座標,disabled 預設無影響——但為一致建議改 `hs=HumanizeSettings(enabled=False)`,可選)。

`test_windows_device_swipe_delegates` 找到:
```python
    monkeypatch.setattr("device.windows.scale_to_client", lambda hwnd, x, y: (x * 2, y * 2))
    fake_input = MagicMock()
    monkeypatch.setattr("device.windows.SendInputBackend", lambda: fake_input)

    dev = WindowsDeviceBackend(hwnd=42, capture_method="bitblt")
    dev.swipe(100, 50, 200, 60, duration=0.3)
```
替換為:
```python
    monkeypatch.setattr("device.windows.scale_to_client", lambda hwnd, x, y: (x * 2, y * 2))
    fake_input = MagicMock()
    monkeypatch.setattr("device.windows.SendInputBackend", lambda hs=None: fake_input)

    dev = WindowsDeviceBackend(hwnd=42, capture_method="bitblt", hs=HumanizeSettings(enabled=False))
    dev.swipe(100, 50, 200, 60, duration=0.3)
```

- [ ] **Step 6: 跑全部 device 測試確認通過**

Run: `pytest tests/test_device.py -v`
Expected: 全部 PASS(既有 windows/adb 精確測試 + 新增人性化測試)

- [ ] **Step 7: 提交**

```bash
git add input/sendinput.py device/windows.py tests/test_device.py
git commit -m "feat(windows): 貝茲軌跡+加減速 點擊/滑動,位置抖動注入"
```

---

## Task 5: `create_device` 組裝 `HumanizeSettings` 注入後端

**Files:**
- Modify: `device/__init__.py`
- Test: `tests/test_device.py`

**Interfaces:**
- Consumes: Task 1 `HumanizeSettings`;Task 2 `AppConfig.humanize_*`;Task 3/4 後端建構子收 `hs`。
- Produces: `_humanize_settings(config) -> HumanizeSettings`;`create_device` 將 `hs` 傳給 `WindowsDeviceBackend(hwnd, capture_method, hs)` 與 `AdbDeviceBackend(client, hs)`。

- [ ] **Step 1: 寫失敗測試(附加至 `tests/test_device.py`)**

```python
from config import AppConfig
from device import _humanize_settings


def test_humanize_settings_maps_from_config():
    cfg = AppConfig._from_dict({
        "humanize_enabled": False,
        "humanize_jitter_px": 15,
        "humanize_swipe_jitter_px": 25,
        "humanize_double_click_spread": 0.05,
        "humanize_swipe_duration_spread": 0.06,
        "humanize_curve_strength": 0.4,
        "humanize_move_steps": 20,
    })
    hs = _humanize_settings(cfg)
    assert hs.enabled is False
    assert hs.jitter_px == 15
    assert hs.swipe_jitter_px == 25
    assert hs.double_click_gap == 0.05     # 固定,不暴露
    assert hs.double_click_spread == 0.05
    assert hs.swipe_duration_spread == 0.06
    assert hs.curve_strength == 0.4
    assert hs.move_steps == 20


def test_create_device_windows_passes_humanize_settings(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "device.WindowsDeviceBackend",
        lambda hwnd, capture_method="auto", hs=None: captured.setdefault("hs", hs),
    )
    monkeypatch.setattr("device.find_game_window", lambda title: 999)
    cfg = AppConfig._from_dict({"platform": "windows", "humanize_enabled": False, "humanize_jitter_px": 99})
    create_device(cfg)
    assert captured["hs"].enabled is False
    assert captured["hs"].jitter_px == 99


def test_create_device_adb_passes_humanize_settings(monkeypatch):
    captured = {}
    monkeypatch.setattr("device.AdbDeviceBackend", lambda client, hs=None: captured.setdefault("hs", hs))
    monkeypatch.setattr("device.AdbClient", lambda **kw: object())
    cfg = AppConfig._from_dict({"platform": "adb", "humanize_enabled": False})
    create_device(cfg)
    assert captured["hs"].enabled is False
```

- [ ] **Step 2: 更新既有 factory 測試 patch 收 `hs`**

既有 `test_create_device_windows` 用 `lambda hwnd, capture_method="auto": ...`(不收 hs),現在 `create_device` 會傳 `hs`,須改:

找到:
```python
    monkeypatch.setattr("device.WindowsDeviceBackend", lambda hwnd, capture_method="auto": ("win", hwnd, capture_method))
    monkeypatch.setattr("device.find_game_window", lambda title: 999)
    cfg = MagicMock(); cfg.platform = "windows"; cfg.window_title = "X"; cfg.capture_method = "bitblt"
    dev = create_device(cfg)
    assert dev == ("win", 999, "bitblt")
```
替換為:
```python
    monkeypatch.setattr("device.WindowsDeviceBackend", lambda hwnd, capture_method="auto", hs=None: ("win", hwnd, capture_method))
    monkeypatch.setattr("device.find_game_window", lambda title: 999)
    cfg = AppConfig._from_dict({"platform": "windows", "capture_method": "bitblt"})
    dev = create_device(cfg)
    assert dev == ("win", 999, "bitblt")
```

既有 `test_create_device_adb` 找到:
```python
    monkeypatch.setattr("device.AdbDeviceBackend", lambda client: built.setdefault("client", client))
    fake_client = object()
    monkeypatch.setattr("device.AdbClient", lambda **kw: fake_client)
    cfg = MagicMock()
    cfg.platform = "adb"; cfg.adb_path = None; cfg.adb_connect = None; cfg.adb_serial = None
    dev = create_device(cfg)
    assert built["client"] is fake_client
```
替換為:
```python
    monkeypatch.setattr("device.AdbDeviceBackend", lambda client, hs=None: built.setdefault("client", client))
    fake_client = object()
    monkeypatch.setattr("device.AdbClient", lambda **kw: fake_client)
    cfg = AppConfig._from_dict({"platform": "adb"})
    dev = create_device(cfg)
    assert built["client"] is fake_client
```

> `test_create_device_windows_no_window_raises` 與 `test_create_device_unknown_platform_raises` 用 `MagicMock` cfg,因 `find_game_window` 回 None / platform 不符,`_humanize_settings` 不會被呼叫或之後才呼叫——`unknown_platform` 在 `_humanize_settings` 之後才 raise,故會先呼叫 `_humanize_settings(MagicMock)`,欄位為 MagicMock 物件但 dataclass 不校驗,不爆錯。維持原樣即可。

- [ ] **Step 3: 跑測試確認失敗**

Run: `pytest tests/test_device.py::test_humanize_settings_maps_from_config -v`
Expected: FAIL(`ImportError: cannot import name '_humanize_settings'`)

- [ ] **Step 4: 實作 `device/__init__.py` — 組裝 + 注入**

完整替換 `device/__init__.py` 內容為:
```python
"""設備門面套件 — 統一截圖/輸入/縮放/生命週期,平台無關。"""

from __future__ import annotations

from config import AppConfig
from device.adb import AdbDeviceBackend
from device.adb_client import AdbClient
from device.base import DeviceBackend, DeviceError
from device.humanize import HumanizeSettings
from device.windows import WindowsDeviceBackend, find_game_window

__all__ = ["DeviceBackend", "DeviceError", "create_device"]


def _humanize_settings(config: AppConfig) -> HumanizeSettings:
    """從 AppConfig 扁平欄位組裝 HumanizeSettings,注入後端。

    double_click_gap 固定 0.05(不暴露至 config)。
    """
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


def create_device(config: AppConfig) -> DeviceBackend:
    """依 config.platform 建立設備後端,注入人性化設定。"""
    hs = _humanize_settings(config)
    if config.platform == "windows":
        hwnd = find_game_window(config.window_title)
        if not hwnd:
            raise DeviceError("找不到遊戲視窗，請確認遊戲已開啟")
        return WindowsDeviceBackend(hwnd, config.capture_method, hs)
    if config.platform == "adb":
        client = AdbClient(
            adb_path=config.adb_path,
            connect=config.adb_connect,
            serial=config.adb_serial,
        )
        return AdbDeviceBackend(client, hs)
    raise DeviceError(f"不支持的平台: {config.platform}")
```

- [ ] **Step 5: 跑全部 device 測試確認通過**

Run: `pytest tests/test_device.py -v`
Expected: 全部 PASS

- [ ] **Step 6: 提交**

```bash
git add device/__init__.py tests/test_device.py
git commit -m "feat(device): create_device 組裝 HumanizeSettings 注入後端"
```

---

## Task 6: flow 節奏強化(`short_sleep` + `maybe_pause`)

**Files:**
- Modify: `automation/flow.py`
- Test: `tests/test_flow.py`

**Interfaces:**
- Consumes: `device.humanize.roll`、`random_gap`(Task 1);`config.humanize_enabled`、`humanize_pause_chance`、`humanize_pause_duration`、`humanize_pause_spread`(Task 2)。
- Produces: `ShopFlow.short_sleep`(抖動隨 `humanize_enabled` 切換範圍);`ShopFlow.maybe_pause()`;主循環 `run()` 開頭呼叫 `maybe_pause()`。

- [ ] **Step 1: 寫失敗測試(附加至 `tests/test_flow.py`)**

```python
def test_maybe_pause_noop_when_disabled():
    flow, *_ = _mk_flow()
    flow.config.humanize_enabled = False
    import automation.flow as flowmod
    slept = []
    flowmod.time.sleep = lambda s: slept.append(s)   # 直接替換模組 sleep
    flow.maybe_pause()
    assert slept == []


def test_maybe_pause_sleeps_when_rolled(monkeypatch):
    flow, *_ = _mk_flow()
    flow.config.humanize_enabled = True
    flow.config.humanize_pause_chance = 0.5
    flow.config.humanize_pause_duration = 2.0
    flow.config.humanize_pause_spread = 0.0
    monkeypatch.setattr("automation.flow.humanize.roll", lambda chance: True)
    slept = []
    monkeypatch.setattr("automation.flow.time.sleep", lambda s: slept.append(s))
    flow.maybe_pause()
    assert len(slept) == 1
    assert 2.0 - 0.0 - 1e-9 <= slept[0] <= 2.0 + 0.0 + 1e-9


def test_short_sleep_uses_wider_jitter_when_enabled(monkeypatch):
    flow, *_ = _mk_flow()
    flow.config.humanize_enabled = True
    flow.config.short_sleep_base = 0.0
    captured = {}
    monkeypatch.setattr("automation.flow.random.uniform", lambda a, b: captured.setdefault("range", (a, b)))
    monkeypatch.setattr("automation.flow.time.sleep", lambda s: None)
    flow.short_sleep(1.0)
    assert captured["range"] == (-0.3, 0.6)


def test_short_sleep_uses_legacy_jitter_when_disabled(monkeypatch):
    flow, *_ = _mk_flow()
    flow.config.humanize_enabled = False
    flow.config.short_sleep_base = 0.0
    captured = {}
    monkeypatch.setattr("automation.flow.random.uniform", lambda a, b: captured.setdefault("range", (a, b)))
    monkeypatch.setattr("automation.flow.time.sleep", lambda s: None)
    flow.short_sleep(1.0)
    assert captured["range"] == (-0.2, 0.3)
```

- [ ] **Step 2: 更新 `_mk_flow` 設 `humanize_enabled=False`(避免 MagicMock config 觸發 maybe_pause 的 float 比較 TypeError)**

找到 `tests/test_flow.py` 中 `_mk_flow` 的 config 設定區塊:
```python
    config = MagicMock()
    config.match_threshold_location = 0.9
    config.match_threshold_button = 0.85
    config.match_threshold_confirm = 0.9
    config.match_threshold_refresh = 0.8
    config.wait_timeout = 0.1
    config.wait_timeout_long = 0.2
    config.max_retry = 2
    config.swipe_fail_limit = 5
    config.short_sleep_base = 0.0
    config.scan_roi_tuple = None
    config.button_roi_tuple = None
```
在 `config.button_roi_tuple = None` 之後新增:
```python
    config.humanize_enabled = False       # 測試時關閉人性化,流程可預測
    config.humanize_pause_chance = 0.0
    config.humanize_pause_duration = 0.0
    config.humanize_pause_spread = 0.0
```

- [ ] **Step 3: 跑測試確認失敗**

Run: `pytest tests/test_flow.py::test_maybe_pause_noop_when_disabled -v`
Expected: FAIL(`AttributeError: 'ShopFlow' object has no attribute 'maybe_pause'`)

- [ ] **Step 4: 實作 `automation/flow.py` — 匯入 humanize + 改 short_sleep + 加 maybe_pause + 主循環呼叫**

在 `automation/flow.py` 匯入區(現有 `import random`、`import time` 之後)新增:
```python
from device import humanize
```

找到 `short_sleep` 方法:
```python
    def short_sleep(self, multiplier: float = 1.0) -> None:
        """帶隨機抖動的延遲，時長 = config.short_sleep_base * multiplier + 抖動。"""
        delay = self.config.short_sleep_base * multiplier + random.uniform(-0.2, 0.3)
        time.sleep(max(0.0, delay))  # 防禦負值（base 過小時抖動可能為負）
```
替換為:
```python
    def short_sleep(self, multiplier: float = 1.0) -> None:
        """帶隨機抖動的延遲，時長 = config.short_sleep_base * multiplier + 抖動。

        humanize 啟用時擴大且不對稱的抖動範圍(-0.3,0.6);關閉時退回原 (-0.2,0.3)。
        """
        if self.config.humanize_enabled:
            jitter = random.uniform(-0.3, 0.6)
        else:
            jitter = random.uniform(-0.2, 0.3)
        delay = self.config.short_sleep_base * multiplier + jitter
        time.sleep(max(0.0, delay))  # 防禦負值（base 過小時抖動可能為負）

    def maybe_pause(self) -> None:
        """以機率隨機停頓,模擬人類「看一下再繼續」。humanize 關閉時直接返回。"""
        if not self.config.humanize_enabled:
            return
        if humanize.roll(self.config.humanize_pause_chance):
            time.sleep(humanize.random_gap(
                self.config.humanize_pause_duration,
                self.config.humanize_pause_spread,
            ))
```

找到 `run` 方法的主循環:
```python
        while self.ctx.should_continue:
            state = self.ctx.state
```
替換為:
```python
        while self.ctx.should_continue:
            self.maybe_pause()
            state = self.ctx.state
```

- [ ] **Step 5: 跑全部 flow 測試確認通過**

Run: `pytest tests/test_flow.py -v`
Expected: 全部 PASS(既有 5 個 + 新增 4 個)

- [ ] **Step 6: 提交**

```bash
git add automation/flow.py tests/test_flow.py
git commit -m "feat(flow): short_sleep 抖動擴大 + maybe_pause 偶爾停頓"
```

---

## Task 7: 文件同步(`CLAUDE.md` + `README.md`)

**Files:**
- Modify: `CLAUDE.md`、`README.md`

**Interfaces:**
- Consumes: 前 6 個任務的最終介面。
- Produces: 文件反映 `device/humanize.py` 模組與 `humanize_*` 設定。

無測試(純文件)。

- [ ] **Step 1: `CLAUDE.md` — 模組職責表新增 `device/humanize.py`**

在「模組職責」表格中,`device/__init__.py` 列之前新增一列:
```markdown
| `device/humanize.py` | 人性化純函數(jitter/bezier/ease/random_gap/roll)+ `HumanizeSettings` dataclass,兩後端與 flow 共用 |
```

- [ ] **Step 2: `CLAUDE.md` — Configuration 段新增 `humanize_*` 說明**

在 Configuration 段關鍵欄位清單中(`swipe_fail_limit` 那行之後)新增:
```markdown
- `humanize_enabled` — 人性化(降低機器特徵)總開關,預設 `true`;`false` 位元級退回舊行為
- `humanize_jitter_px` / `humanize_swipe_jitter_px` — 點擊/滑動起終點的位置抖動半徑(參考解析度 px)
- `humanize_curve_strength` / `humanize_move_steps` — 僅 Windows:貝茲軌跡弧度與取樣點數
- `humanize_pause_chance` / `humanize_pause_duration` / `humanize_pause_spread` — 主循環偶爾停頓的機率與時長
```

- [ ] **Step 3: `CLAUDE.md` — 「設備後端(DeviceBackend)」段補註人性化分層**

在該段末尾(「`capture/` 與 `input/` 套件為 Windows 後端所用,上層不再直接呼叫。」之後)新增一段:
```markdown

### 人性化(降低機器特徵)

點擊/滑動的位置抖動、軌跡與時序隨機化由各後端吸收(共用純函數集中於 `device/humanize.py`),flow 僅負責節奏(`short_sleep` 抖動擴大 + 主循環 `maybe_pause`)。Windows 後端生成貝茲曲線游標軌跡 + 加減速;ADB 後端務實方案(位置/起終點抖動 + 時序隨機,軌跡維持系統直線)。`humanize_enabled=false` 可完全關閉、位元級退回舊行為。
```

- [ ] **Step 4: `README.md` — 新增「人性化/降低機器特徵」段落**

在 README 適當位置(設定說明區塊內)新增段落,內容大意:
```markdown
## 人性化(降低機器特徵)

工具預設啟用輸入人性化,降低自動化行為的機器特徵:點擊位置隨機抖動、滑鼠沿貝茲曲線移動(Windows)、滑動加減速、雙擊間隔與操作節奏隨機化。這會讓刷商店整體耗時增加約 20~40%。

如需關閉(回到最快、最規律的行為),在 `config.json` 設:

```json
{ "humanize_enabled": false }
```

相關可調參數見 `config.py` 的 `humanize_*` 欄位(抖動強度、停頓機率等)。
```
(實際排版配合 README 既有標題層級。)

- [ ] **Step 5: 提交**

```bash
git add CLAUDE.md README.md
git commit -m "docs: 補充人性化模組與 humanize_* 設定說明"
```

---

## 驗收準則

- [ ] `pytest` 全綠(既有測試 + 新增 test_humanize/test_config/test_device/test_flow)。
- [ ] `humanize_enabled=false` 時,Windows 點擊瞬移、滑動勻速直線、ADB tap 精確、short_sleep 原範圍、無 maybe_pause——行為等同改動前。
- [ ] `humanize_enabled=true`(預設)時:Windows 游標可見弧線移動 + 加減速;點擊位置每次略不同;ADB tap 座標每次略不同;偶爾停頓。
- [ ] 舊 `config.json`(無 `humanize_*`)載入不報錯,預設啟用。
- [ ] Windows 與 ADB 兩模式手動跑一次完整刷商店流程,確認正常購買/滑動/刷新。
