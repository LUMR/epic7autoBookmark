# 人性化开关上界面 — 设计

日期：2026-07-08
状态：已批准，待实施

## 背景与目标

当前「人性化（降低机器特征）」总开关 `humanize_enabled` 只存在于 `config.json` / `AppConfig`，普通用户无法在软件界面上切换，必须手改配置文件。本设计把该总开关暴露到 GUI，让用户无需编辑文件即可选择下次任务是否启用拟人化。

## 需求（已与用户确认）

1. **作用时机**：仅「下次点开始」时生效。运行中切换不影响当前任务。
2. **不持久化**：勾选状态不写回 `config.json`。每次打开软件，checkbox 回到 `config.json` 中 `humanize_enabled` 的当前值（默认 `True` → 默认勾选）。
3. **范围**：只暴露总开关 `humanize_enabled`。其余人性化参数（`jitter_px`、`curve_strength`、`pause_*` 等）仍只在 `config.json` 配置，不上界面。
4. **位置**：放在「开始」按钮左侧（functionTab 底部，y≈410）。

## 现状分析（为什么是最小侵入）

人性化分两层生效：

- **后端层**（`device/windows.py`、`device/adb.py`）：`HumanizeSettings.enabled` 在每次 `click`/`swipe` 读取，控制抖动 / 轨迹 / 间隔。由 `create_device(config)` 在 `device/__init__.py` 的 `_humanize_settings()` 一次性注入后端实例。
- **flow 层**（`automation/flow.py`）：`ShopFlow` 直接读 `self.config.humanize_enabled`，控制 `short_sleep()` 抖动幅度与 `maybe_pause()` 偶尔停顿。

`worker.run()` 每次执行都 `config = AppConfig.load()` → `create_device(config)` → `ShopFlow(..., config)`。因此**只要在 `create_device` 之前覆盖 `config.humanize_enabled`**，flow 层（读同一 config 对象）与 device 层（factory 从同一 config 组装 `HumanizeSettings`）都会自然拿到新值。无需修改 `AppConfig`、`HumanizeSettings`、`create_device`、后端、flow。

## 设计

### 数据流

```
GUI checkbox ──(点开始)──► worker.setVariable(..., humanize_enabled)
                                   │
                                   ▼
worker.run(): config = AppConfig.load()
              config.humanize_enabled = self.humanize_enabled   ← 关键一行
              create_device(config)   ──► HumanizeSettings.enabled
              ShopFlow(..., config)   ──► flow 读 config.humanize_enabled
```

### 改动清单

#### `gui.py`
1. `setupUi()`：新增 `self.humanizeCheckBox = QCheckBox(functionTab)`，定位在「开始」按钮左侧（y≈410，左对齐）。
2. `retranslateUi()`：设置 checkbox 文字为「人性化」。
3. 默认勾选状态：读取 `AppConfig.load()` 的 `humanize_enabled`（沿用 `setupUi` 开头已有的 `config = AppConfig.load()` / `defaults` 模式，把 `humanize_enabled` 一并取出）。若加载失败回退到勾选。
4. `_handle_start()`：读取 `self.humanizeCheckBox.isChecked()`，作为新参数传入 `worker.setVariable(...)`。
5. `startProperty()`：在禁用列表中加入 `self.humanizeCheckBox.setDisabled(isDisabled)`（运行中禁用，避免误以为运行中能切）。

#### `worker.py`
1. `setVariable()`：增加参数 `humanize_enabled: bool`，存为 `self.humanize_enabled`。
2. `run()`：在 `config = AppConfig.load()` 之后、`create_device(config)` 之前，加 `config.humanize_enabled = self.humanize_enabled`。

#### 不改动
`config.py`、`device/humanize.py`、`device/__init__.py`、`device/windows.py`、`device/adb.py`、`automation/flow.py` —— 全部零改动。

## 边界行为

- **运行中禁用 checkbox**：`startProperty(True)` 时与 radio / input 一并禁用；停止后恢复。运行中切换无效，符合「下次开始生效」语义。
- **加载失败回退**：`AppConfig.load()` 抛异常时 checkbox 默认勾选（与现有 `defaults` 回退分支一致的安全策略）。
- **多语言文字**：checkbox 文字随 `retranslateUi` 走，与其他控件一致。

## 测试策略

- **GUI 层**：按项目惯例（CLAUDE.md：GUI 靠手动验证）手动验证：
  - checkbox 存在、默认勾选（与 `config.json` 的 `humanize_enabled` 一致）。
  - 勾选/取消后点「开始」，任务以对应状态运行（开=有抖动/停顿，关=位元级行为）。
  - 运行中 checkbox 被禁用，停止后恢复。
- **worker override 逻辑**（可选自动化）：验证「load 后赋值 → 传入 `create_device` 的 config.humanize_enabled 与 GUI 传入值一致」。可用现有 `tests/fakes.py` 的 `FakeDevice` 或 mock 工厂。因核心只是一行赋值，若不易干净抽出则跳过，避免过度抽象。

## 验收标准

1. 界面上出现人性化 checkbox，默认勾选状态 = `config.json` 的 `humanize_enabled`。
2. 取消勾选后点「开始」，本次任务的点击/滑动无抖动、无贝茲轨迹（Windows）、`short_sleep` 抖动退回 `(-0.2, 0.3)`、`maybe_pause` 不停顿（即位元级退回）。
3. 勾选后点「开始」，人性化照常生效。
4. 运行中 checkbox 禁用；停止后恢复可点。
5. 不写 `config.json`；重启软件 checkbox 回到 config 默认值。
6. `AppConfig` / `HumanizeSettings` / `create_device` / 后端 / flow 源码无改动。
