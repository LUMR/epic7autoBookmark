# 人性化开关上界面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 GUI「开始」按钮左侧加一个人性化总开关 checkbox，勾选状态在下次点「开始」时生效（覆盖 `config.humanize_enabled`），不写回 `config.json`、运行中禁用。

**Architecture:** GUI checkbox → `worker.setVariable()` 新增 `humanize_enabled` 参数 → 新增 `Worker._prepare_config()` 在 `AppConfig.load()` 之后覆盖 `config.humanize_enabled` 一行 → 既有的 `create_device(config)`（组装 `HumanizeSettings.enabled`）与 `ShopFlow(..., config)`（读 `config.humanize_enabled`）自然生效。`config.py` / `device/*` / `automation/flow.py` 零改动。

**Tech Stack:** Python 3.9+, PyQt6, pytest, dataclasses。

## Global Constraints

（摘自 spec `docs/superpowers/specs/2026-07-08-humanize-toggle-ui-design.md`，每个 task 隐含遵守）

- 作用时机：**下次点「开始」才生效**；运行中切换无效（且运行中 checkbox 被禁用）。
- **不持久化**：不写回 `config.json`；重启软件 checkbox 回到 `config.json` 的 `humanize_enabled`（默认 `True`）。
- **只暴露总开关** `humanize_enabled`；其余人性化参数仍只在 `config.json`。
- GUI 位置：「开始」按钮左侧（functionTab 底部，约 y=412）。
- 默认勾选 = `config.json` 的 `humanize_enabled`；`AppConfig.load()` 失败时回退为勾选（`True`）。
- **不改动** `config.py` / `device/humanize.py` / `device/__init__.py` / `device/windows.py` / `device/adb.py` / `automation/flow.py`。
- 提交信息不署名（项目 CLAUDE.md 规定）。

## File Structure

- **Modify** `worker.py` — `Worker` 类：`__init__` 加 `self.humanize_enabled` 默认值；`setVariable()` 加参数；新增 `_prepare_config()`；`run()` 改用 `_prepare_config()`。
- **Modify** `gui.py` — `Ui_Main`：`setupUi()` 加 checkbox + 默认勾选；`retranslateUi()` 加文字；`startProperty()` 加禁用；`_handle_start()` 传值。
- **Create** `tests/test_worker.py` — 覆盖 `_prepare_config()` 的 override 行为（首个触碰 Qt 的测试，顶部建 `QApplication` guard）。

---

## Task 1: Worker — 接收并应用人性化开关

**Files:**
- Modify: `worker.py`
- Test: `tests/test_worker.py`（新建）

**Interfaces:**
- Produces: `Worker.setVariable(self, startMode: int, expectNum: int, moneyNum: int, stoneNum: int, humanize_enabled: bool) -> None`
- Produces: `Worker._prepare_config(self) -> AppConfig`（load 后覆盖 `humanize_enabled`）
- Produces: `Worker.humanize_enabled: bool`（`__init__` 默认 `True`）

- [ ] **Step 1: 写失败的测试（新建 `tests/test_worker.py`）**

```python
"""Worker 測試 — 驗證人性化開關從 setVariable 正確傳到 config。"""
from PyQt6 import QtWidgets

from config import AppConfig
from worker import Worker

# 首個觸碰 Qt 的測試:確保 QThread 可實例化(不啟動事件循環)。
_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_prepare_config_overrides_humanize(monkeypatch):
    """setVariable 傳入的 humanize_enabled 必須覆蓋 AppConfig.load() 的值。"""
    base = AppConfig._from_dict({"humanize_enabled": True})
    monkeypatch.setattr(AppConfig, "load", lambda: base)

    w = Worker()
    w.setVariable(
        startMode=3, expectNum=99, moneyNum=1000, stoneNum=30000,
        humanize_enabled=False,
    )

    cfg = w._prepare_config()
    assert cfg.humanize_enabled is False
    # 其他欄位維持 load 結果,不受覆蓋影響
    assert cfg.platform == "windows"


def test_prepare_config_default_humanize_true(monkeypatch):
    """未呼叫 setVariable 時,_prepare_config 使用 __init__ 預設(True)。"""
    base = AppConfig._from_dict({"humanize_enabled": False})
    monkeypatch.setattr(AppConfig, "load", lambda: base)

    w = Worker()  # 不呼叫 setVariable
    cfg = w._prepare_config()
    assert cfg.humanize_enabled is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_worker.py -v`
Expected: FAIL — `Worker.setVariable() got an unexpected keyword argument 'humanize_enabled'`（或 `_prepare_config` 不存在 / `AttributeError`）。

- [ ] **Step 3: 改 `worker.py` — `__init__` 加默认值**

在 `worker.py` 的 `Worker.__init__` 中，现有字段之后加一行：

```python
    def __init__(self):
        super().__init__()
        self.startMode = 0
        self.expectNum = 0
        self.moneyNum = 0
        self.stoneNum = 0
        self.humanize_enabled = True   # 預設與 AppConfig.humanize_enabled 一致
        self._running = False
        self._ctx: ShopContext | None = None
```

- [ ] **Step 4: 改 `worker.py` — `setVariable()` 加参数**

```python
    def setVariable(
        self,
        startMode: int,
        expectNum: int,
        moneyNum: int,
        stoneNum: int,
        humanize_enabled: bool,
    ) -> None:
        self.startMode = startMode
        self.expectNum = expectNum
        self.moneyNum = moneyNum
        self.stoneNum = stoneNum
        self.humanize_enabled = humanize_enabled
```

- [ ] **Step 5: 改 `worker.py` — 新增 `_prepare_config()` 方法**

在 `setVariable` 与 `stop` 之间加入：

```python
    def _prepare_config(self) -> AppConfig:
        """載入 config 並套用 GUI 的人性化開關。

        在 create_device 之前覆蓋 config.humanize_enabled,使 flow(讀 config)
        與 device(factory 從 config 組裝 HumanizeSettings)同時生效。
        """
        config = AppConfig.load()
        config.humanize_enabled = self.humanize_enabled
        return config
```

- [ ] **Step 6: 改 `worker.py` — `run()` 改用 `_prepare_config()`**

在 `run()` 中，把：

```python
            # 加载配置
            config = AppConfig.load()
```

替换为：

```python
            # 加载配置(GUI 人性化開關在此套用)
            config = self._prepare_config()
```

- [ ] **Step 7: 跑测试确认通过**

Run: `pytest tests/test_worker.py -v`
Expected: PASS（2 passed）。

- [ ] **Step 8: 跑全量回归**

Run: `pytest -q`
Expected: 全绿（新增 2 个 worker 测试，其余既有测试不受影响）。

- [ ] **Step 9: 提交**

```bash
git add worker.py tests/test_worker.py
git commit -m "feat(worker): 接收人性化開關並於 _prepare_config 覆蓋 config"
```

---

## Task 2: GUI — 人性化 checkbox 接线

**Files:**
- Modify: `gui.py`

**Interfaces:**
- Consumes: `Worker.setVariable(..., humanize_enabled: bool)`（Task 1 产出）

> 本任务按项目惯例（CLAUDE.md：GUI 靠手动验证，无 pytest-qt）不写自动化测试，改以手动验证清单收尾。

- [ ] **Step 1: `setupUi()` — config 加载处记录人性化默认值**

在 `gui.py` 的 `setupUi` 开头，把：

```python
        # 加载配置获取默认值
        try:
            config = AppConfig.load()
            defaults = config.ui_defaults
        except Exception:
            defaults = {
                "money": "100000000",
                "stone": "30000",
                "covenant": "0",
                "mystic": "0",
                "stone_usage": "99",
            }
```

替换为：

```python
        # 加载配置获取默认值
        try:
            config = AppConfig.load()
            defaults = config.ui_defaults
            humanize_default = config.humanize_enabled
        except Exception:
            defaults = {
                "money": "100000000",
                "stone": "30000",
                "covenant": "0",
                "mystic": "0",
                "stone_usage": "99",
            }
            humanize_default = True
```

- [ ] **Step 2: `setupUi()` — 在开始按钮之后创建 checkbox**

在 `self.startButton` 创建块之后、`self.tabWidget.addTab(self.functionTab, "")` 之前，加入：

```python
        # 人性化开关(开始按钮左侧)
        self.humanizeCheckBox = QtWidgets.QCheckBox(self.functionTab)
        self.humanizeCheckBox.setGeometry(QtCore.QRect(20, 412, 111, 20))
        self.humanizeCheckBox.setFont(font_main)
        self.humanizeCheckBox.setChecked(humanize_default)
        self.humanizeCheckBox.setObjectName("humanizeCheckBox")
```

- [ ] **Step 3: `retranslateUi()` — 设置 checkbox 文字**

在 `retranslateUi` 中，`self.startButton.setText(...)` 那一行之后加入：

```python
        self.humanizeCheckBox.setText(_translate("Main", "人性化"))
```

- [ ] **Step 4: `startProperty()` — 运行中禁用 checkbox**

在 `startProperty` 方法末尾的输入框禁用列表之后，加入：

```python
        self.humanizeCheckBox.setDisabled(isDisabled)
```

- [ ] **Step 5: `_handle_start()` — 读取 checkbox 并传入 worker**

在 `_handle_start` 末尾，把：

```python
        self.worker.setVariable(startMode, expectNum, moneyNum, stoneNum)
        self.worker.start()
```

替换为：

```python
        humanize = self.humanizeCheckBox.isChecked()
        self.worker.setVariable(startMode, expectNum, moneyNum, stoneNum, humanize)
        self.worker.start()
```

- [ ] **Step 6: 语法检查（无 GUI 也能跑的导入/编译校验）**

Run: `python -c "import gui; print('ok')"`
Expected: 输出 `ok`，无异常。（若环境无显示，PyQt6 导入与类定义仍可完成；仅 `QApplication` 创建窗口需显示环境。）

- [ ] **Step 7: 手动验证清单**

启动 `python main.py`（或 EXE），逐项确认：

1. 「功能」Tab 底部、「开始」按钮左侧出现「人性化」checkbox。
2. checkbox 默认勾选状态 = `config.json` 的 `humanize_enabled`（仓库默认 `true` → 勾选）。
3. 取消勾选 → 点「开始」：本次任务点击/滑动无抖动、无贝茲轨迹（Windows）、节奏明显更快（位元级退回）。
4. 勾选 → 点「开始」：人性化照常（有抖动/偶尔停顿）。
5. 任务运行中 checkbox 被禁用（灰色不可点）；停止后恢复可点。
6. 重启软件：checkbox 回到 `config.json` 的值（未被上次操作改动）。
7. （可选）手改 `config.json` 为 `"humanize_enabled": false` 后重启：checkbox 默认不勾选。

- [ ] **Step 8: 提交**

```bash
git add gui.py
git commit -m "feat(gui): 人性化開關 checkbox(下次開始生效)"
```

---

## 完成标准

- Task 1 全绿（`pytest tests/test_worker.py` + 全量 `pytest`）。
- Task 2 手动验证清单全过。
- `config.py` / `device/*` / `automation/flow.py` 在 `git diff` 中无改动。
- 每个任务各一次提交，提交信息无署名。
