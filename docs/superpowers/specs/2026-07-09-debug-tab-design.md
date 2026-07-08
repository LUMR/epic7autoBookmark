# 新增调试（檢測）Tab 页 — 设计

日期：2026-07-09
状态：已批准，待实施
需求来源：`docs/superpowers/feats/feat1.md`

## 背景与目标

当前 GUI 只有「功能」「簡介」两个 Tab，缺少校验模板匹配效果的手段。开发/调试时无法直观看到「当前游戏画面里每种书签、按钮的匹配置信度究竟是多少」，也无法对已保存的游戏截图做批量回归。本设计新增第三个 Tab「檢測」，提供三个能力：

1. **檢測**：截当前游戏画面，计算 6 种元素各自的匹配值，并自动勾选匹配最高的一项（有书签时优先书签）。
2. **保存截圖**：把当前截图按勾选类型的前缀命名保存为素材。
3. **回歸測試**：对素材目录中所有图像素材逐一匹配，校验匹配值是否达标，汇总结果。

## 需求（已与用户确认）

来自 `feat1.md`，要点：

- 页面显示每种书签/按钮的名称与匹配值，每项配一个单选框。
- 6 种元素及素材命名前缀：
  - 购买按钮 `buyButton`
  - 购买确认按钮 `buyConfirm`
  - 神秘书签 `mystic`
  - 圣约书签 `covenant`
  - 刷新按钮 `refresh`
  - 刷新确认按钮 `refreshYes`
- **[檢測]**：计算每项匹配值；勾选匹配值最高的一项（有书签时优先选书签）；可人为改选。
- **[保存截圖]**：保存当前游戏页面截图，按勾选的单选框（即类型前缀）命名素材文件。
- **[回歸測試]**：对所有图像素材做回归，检测匹配值是否达标；完成后汇总显示结果。
- 图像素材统一存于同一目录，按所匹配的书签/按钮命名（如 `covenant_1.png`、`covenant_2.png`）。

## 现状分析

- **GUI**（`gui.py`）：`QTabWidget` 含「功能」「簡介」两 Tab，手写绝对定位（`setGeometry`），主窗口固定 310×500、繁中介面。新增 Tab 需放大窗口并保持绝对定位风格。
- **匹配器**（`detection/matcher.py`）：`TemplateMatcher.match(image, template, threshold, name, roi)` 在分数低于 `threshold` 时返回 `None`（不返回分数）。调试页要显示**原始最高分**，故检测时以接近 0 的阈值调用以拿到真实分数。
- **模板**（`automation/templates.py` / `img/`）：实际模板名为 `covenantLocation`、`mysticLocation`、`buyButton`、`buyConfirmButton`、`refreshButton`、`refreshYesButton`，与需求中的素材前缀（`covenant`/`mystic`/`buyButton`/`buyConfirm`/`refresh`/`refreshYes`）**不同**，需建立映射。`buyButton` 模板存在（`img/buyButton-zh-TW.png`）但主流程 `flow.py` 未使用——调试页仍纳入检测。
- **阈值/ROI**（`config.py`）：`match_threshold_location`(0.9)/`button`(0.85)/`confirm`(0.9)/`refresh`(0.8)；`scan_roi`（书签扫描）/`button_roi`（按钮搜寻）。检测与回归须用与主流程一致的 ROI，结果才有意义。
- **设备**（`device/__init__.py`）：`create_device(config)` 统一 `capture()/click()/swipe()/prepare()/close()`，`capture()` 恒输出 1920×1080 BGR。调试页复用它截屏，平台无关。

## 设计

### 架构概览

- 新增**纯逻辑模块 `automation/inspection.py`**（无 Qt 依赖）：封装前缀↔模板映射、匹配值计算、文件编号、回归判定。GUI 只调用它并显示结果——核心逻辑可单元测试，与现有 matcher/config/flow 的「IO/GUI 分离」惯例一致。
- 复用 `TemplateMatcher`、`TemplateManager`、`AppConfig`、`create_device`，不重复造轮子。
- 调试操作自建临时 device 与自动化 Worker **互斥**（一方运行时另一方禁用）。

### 页面组件（debugTab，绝对定位，沿用现有风格）

```
┌ 功能 ┐ 檢測      簡介
├──────────────────────────┐
│ 項目        分數    勾選   │
│ ○ 聖約書籤  0.92          │   ← 6 行：单选 + 名称 + 分数
│ ○ 神秘書籤  0.11          │     分数≥阈值：粗体/绿；<阈值：灰
│ ● 購買按鈕  0.88          │     单选同组互斥（QButtonGroup）
│ ○ 購買確認  0.03          │
│ ○ 刷新按鈕  0.05          │
│ ○ 刷新確認  0.02          │
│──────────────────────────│
│   [檢測]    [保存截圖]    │
│   [回歸測試]              │
│──────────────────────────│
│ 回歸結果 (QTextBrowser)   │
│ 聖約5/5 神秘3/4 購買8/8…  │
└──────────────────────────┘
```

行顺序固定：聖約書籤、神秘書籤、購買按鈕、購買確認、刷新按鈕、刷新確認。

### 数据流

**[檢測]**
1. `create_device(config)` → `prepare()` → `capture()` 截一张图（1920×1080 BGR）→ `close()`。
2. 对 6 项分别调用 `TemplateMatcher.match`，`threshold` 传极小值（≈0.0）以取**原始最高分**；ROI 用该项对应 ROI（书签→`scan_roi`，按钮类→`button_roi`）。
3. 表格填分数（保留 2 位小数）；分数 ≥ 该项阈值标绿/粗体，<阈值标灰；模板缺失则显示 `N/A`。
4. 按「优先书签」规则自动勾选一项（见下），用户可改选。
5. GUI 缓存本次截图，供「保存截圖」复用（避免重复截屏 / 画面已变动）。

**[保存截圖]**
1. 取检测缓存的截图（无则提示「請先檢測」）。
2. 按当前勾选类型的**前缀**命名：扫描素材目录中该前缀已有文件，取最大序号 +1，存为 `{prefix}_{n}.png`（如 `covenant_3.png`）。
3. PNG 经 `cv2.imencode` + `np.tofile` 写入（兼容中文路径，与模板加载的 `np.fromfile`+`imdecode` 对称）。

**[回歸測試]**
1. 扫描素材目录，按文件名前缀分组（`covenant_` / `mystic_` / `buyButton_` / `buyConfirm_` / `refresh_` / `refreshYes_`）。
2. 每张素材图作为 image，用前缀对应模板 + 对应阈值 + 对应 ROI 匹配，判定通过/不通过。
3. 结果区汇总：每类 X/Y、总通过率；未通过者列出文件名 + 实际分数。

### 前缀 → 模板/阈值/ROI 映射（检测与回归共用）

| 素材前缀 | 模板名 | 阈值字段 | ROI |
|---|---|---|---|
| `covenant` | `covenantLocation` | `match_threshold_location` (0.9) | `scan_roi` |
| `mystic` | `mysticLocation` | `match_threshold_location` (0.9) | `scan_roi` |
| `buyButton` | `buyButton` | `match_threshold_button` (0.85) | `button_roi` |
| `buyConfirm` | `buyConfirmButton` | `match_threshold_button` (0.85) | `button_roi` |
| `refresh` | `refreshButton` | `match_threshold_refresh` (0.8) | `button_roi` |
| `refreshYes` | `refreshYesButton` | `match_threshold_confirm` (0.9) | `button_roi` |

### 「优先书签」勾选规则

1. 书签项（`covenant`/`mystic`）中存在分数 ≥ 其阈值者 → 勾选其中分数最高者。
2. 否则 → 勾选 6 项中分数最高者（仍优先书签：若最高分并列且含书签，取书签）。
3. 所有项均 `N/A` → 不勾选。

## 改动清单

### 新增 `automation/inspection.py`（纯逻辑，无 Qt）

- `INSPECTION_ITEMS`：6 项有序定义，每项含 `(prefix, template_name, threshold_attr, roi_attr, display_name)`。
- 数据类：`ItemScore(prefix, display_name, score: float | None, threshold: float, passed: bool)`、`RegressionReport(per_prefix: dict[str, tuple[int, int]], failures: list[Failure], total: int, passed: int)`。
- `class Inspector`（持有 `templates`、`matcher`、`config`，方法无状态依赖外部传入截图）：
  - `inspect(screenshot) -> list[ItemScore]`：逐项在对应 ROI、threshold≈0.0 匹配，返回原始最高分；模板缺失 → `score=None`。
  - `pick_default(scores) -> str | None`：实现「优先书签」规则。
  - `next_index(directory, prefix) -> int`：扫描目录同前缀文件，返回最大序号 +1（无则 1）。
  - `save_screenshot(screenshot, directory, prefix) -> Path`：`next_index` + `imencode`/`tofile` 写 PNG。
  - `run_regression(directory) -> RegressionReport`：扫描分组、逐张匹配判定。

### 改动 `config.py`

- 新增字段 `regression_assets_dir: str = "./regression"`（有默认值，旧 config 向后兼容）。
- 可选：property `regression_assets_path -> Path`。

### 改动 `gui.py`

- 主窗口 `resize` 到约 420×600；`tabWidget` 及两旧 Tab 尺寸同步放大（保持绝对定位）。
- 新增 `debugTab`：6 行（`QRadioButton` + `QLabel` 名称 + `QLabel` 分数，`QButtonGroup` 互斥）+ 3 个 `QPushButton`（檢測/保存截圖/回歸測試）+ 结果 `QTextBrowser`。文字走 `retranslateUi`，繁中。
- 新增内部轻量 `QThread`（如 `_InspectionWorker`）调用 `Inspector`，通过 `pyqtSignal` 回传结果，避免截屏/批量匹配卡 UI。
- 三个按钮的 slot 实现；检测缓存截图存于 GUI 成员。
- **互斥**：自动化 `Worker.isRunning()` 时禁用调试按钮；调试运行时禁用「開始」按钮。

### 不改动

`detection/matcher.py`、`automation/templates.py`、`automation/flow.py`、`worker.py`、`device/*`、`constants.py` —— 零改动（复用现有接口）。

## 边界行为 / 错误处理

- 截屏失败 / 找不到游戏窗口 → 结果区提示。
- 素材目录不存在或为空 → 回歸測試提示「無素材」。
- 某项模板缺失（如当前语言无 `buyButton`）→ 该项显示 `N/A`，检测跳过、回归该类整组跳过。
- 保存截图时目录不可写 → 提示。
- 未检测就点「保存截圖」→ 提示「請先檢測」。
- 调试与自动化互斥：一方运行时另一方按钮禁用，结束自动恢复。

## 测试策略

- **纯逻辑层**（`tests/test_inspection.py`，沿用 pytest）：
  - 前缀↔模板映射完整性（6 项、字段正确）。
  - `inspect`：用小图 + `FakeDevice`/合成图验证返回原始最高分、模板缺失返回 `None`。
  - `pick_default`：覆盖「书签达标优先」「无书签达标取最高」「并列取书签」「全 N/A」。
  - `next_index`：空目录→1、已有 `covenant_1/2`→3、乱序文件名取最大。
  - `run_regression`：合成素材目录，验证分组、通过/不通过判定、汇总计数。
- **GUI/截屏层**：按项目惯例（CLAUDE.md：GUI 靠手动验证）手动验证三个按钮行为、互斥禁用、分数着色。

## 验收标准

1. GUI 出现第三个 Tab「檢測」，主窗口约 420×600，两旧 Tab 正常显示。
2. [檢測] 截当前画面，6 行显示各自原始匹配值（2 位小数），≥阈值高亮、<阈值变灰、缺失显示 N/A；按「优先书签」规则自动勾选一项，可手动改选。
3. [保存截圖] 把缓存截图按勾选前缀 + 自增序号存为 `{prefix}_{n}.png` 于 `regression_assets_dir`（默认 `./regression`）。
4. [回歸測試] 扫描素材目录，按前缀分组逐张匹配，结果区显示每类 X/Y、总通过率及未通过明细。
5. 三操作在后台线程执行，不卡 UI；运行中相关按钮禁用。
6. 调试与自动化互斥：一方运行时另一方不可启动。
7. `matcher`/`templates`/`flow`/`worker`/`device` 源码零改动；`AppConfig` 仅新增 `regression_assets_dir`（有默认值）。
