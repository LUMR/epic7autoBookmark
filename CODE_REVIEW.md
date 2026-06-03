# 代码审查报告

**项目**: epic7autoBookmark
**审查日期**: 2026-05-28
**审查范围**: 最近一次提交 (9445a4c) 的变更及完整 main.py

---

## 概要

本次审查发现 **8 个问题**，其中 5 个为逻辑 Bug，2 个为代码质量问题，1 个为用户体验问题。最严重的是 `wait_for_stable` 超时后的无效重试和滑动失败时的无限循环。

---

## Bug 类

### 1. `wait_for_stable` 超时后 `continue` 导致无效重试

- **文件**: `main.py:367`
- **严重程度**: 高

当 `wait_for_stable` 返回 False（商店加载动画超时），第 367 行的 `continue` 跳回的是**内层 `retry2`** 循环，而非外层 `retry` 循环。下一轮 retry2 中 `wait_for` 发现确认按钮已消失，立即返回 True，然后再次调用 `wait_for_stable` 又超时。如此循环 MAX_RETRY(20) 次，每次等待 15 秒超时，最多浪费 **5 分钟**。

**影响**: 商店加载较慢时（网络延迟、低配设备），用户被迫等待 5 分钟而非立即重试刷新。

**建议**: 将 `continue` 改为 `break`，退出 retry2 后走到 `else: continue` 回到外层 retry，重新点击刷新按钮。

---

### 2. 滑动失败时无限循环

- **文件**: `main.py:335-404`
- **严重程度**: 高

滑动-刷新循环没有退出条件。如果滑动操作无效（窗口最小化、游戏卡死、画面无变化），代码进入死循环：

```
滑动 → needRefresh=True → 下一轮找不到刷新按钮 → 重置标志 → needRefresh=False → 再滑动 → ...
```

`expectNum`、`moneyNum`、`stoneNum` 在此循环中都不变化，while 循环条件永远为真，唯一退出方式是用户手动点击"停止"。

**影响**: 游戏窗口异常时 CPU 占用 100%，且必须手动干预停止。

**建议**: 加入连续滑动失败计数器，超过阈值（如 5 次）抛出异常退出 Worker。

---

### 3. `worker.terminate()` 泄漏 GDI 资源

- **文件**: `main.py:738`（停止按钮）vs `main.py:100-134`（`capture_window`）
- **严重程度**: 高

`QThread.terminate()` 在 Windows 上调用底层 `TerminateThread`，**不会**执行 Python 的 `finally` 块。`capture_window()` 在 lines 107-111 创建的 DC 和 Bitmap 对象如果在线程被终止时正处于 `try` 块中，`finally` 清理代码不会执行，GDI 资源永远泄漏。

每次泄漏约 3 个 GDI 句柄，多次启停后可耗尽系统 GDI 句柄池（默认上限 10,000），导致所有应用程序窗口渲染异常。

**影响**: 频繁启停工具后，系统出现"内存不足"或窗口渲染错误。

**建议**: 用 `self._running` 标志位替代 `terminate()`。在 `startPressEvent` 中设为 False，在 Worker 的循环中每次迭代检查该标志，实现优雅退出。

---

### 4. 天空石模式下 `expectNum` 可能超支

- **文件**: `main.py:250, 379`
- **严重程度**: 中

天空石模式（startMode=3）每次刷新扣减 3，但用户输入不一定是 3 的倍数。例如用户输入 4：

| 刷新次数 | expectNum 变化 | 实际消耗 |
|---------|---------------|---------|
| 第 1 次  | 4 → 1         | 3 石头  |
| 第 2 次  | 1 → -2        | 6 石头  |
| 退出循环 |               | 共 6 石头 |

用户意图消耗 4 石头，实际消耗了 6 石头。第 380 行的日志 `int(self.expectNum / 3)` 对负数使用向零截断，掩盖了超支。

**影响**: 用户输入非 3 倍数的天空石数量时，实际消耗超出预期。

**建议**: 将 while 条件在模式 3 时改为 `self.expectNum >= 3`，或在 `startPressEvent` 中校验输入为 3 的倍数。

---

### 5. `covenantFound`/`mysticFound` 在购买成功前就设为 True

- **文件**: `main.py:257, 297`
- **严重程度**: 中

找到书签模板匹配后，`covenantFound`/`mysticFound` 标志立即设为 True（lines 257, 297），但此时购买尚未完成。如果购买失败（购买按钮始终不出现、确认超时），flag 仍为 True。后续同一轮扫描中该书签类型被完全跳过，即使它仍在商店中可见。

flag 仅在商店刷新后（lines 383-384）或刷新按钮缺失时（lines 339-340）重置。

**影响**: 购买失败后，该书签被锁定直到商店刷新，浪费 3 天空石做不必要的刷新。

**建议**: 将 `covenantFound = True` / `mysticFound = True` 移到购买成功之后（对应 `break` 语句之前）。

---

## 用户体验问题

### 6. `expectNum=0` 时静默无操作

- **文件**: `main.py:708-724`
- **严重程度**: 低

用户在次数输入框中输入非数字内容（如空字符串、"abc"）时，`isdigit()` 返回 False，`expectNum` 默认为 0。while 循环条件 `self.expectNum > 0` 立即为假，Worker 启动后执行初始化日志，然后直接输出结算摘要（全为 0）并正常结束，无任何错误提示。

**影响**: 用户输入错误后无反馈，误以为正常运行但未找到商品。

**建议**: 在 `startPressEvent` 中增加 `expectNum == 0` 的校验，提示用户输入有效次数。

---

## 代码质量问题

### 7. UI 字体设置重复 16 次

- **文件**: `main.py:430-600`（`setupUi` 方法）
- **严重程度**: 低

完全相同的 4 行字体设置代码在 `setupUi` 中重复 16 次：

```python
font = QtGui.QFont()
font.setFamily("微軟正黑體")
font.setPointSize(12)
widget.setFont(font)
```

每个控件（Main、tabWidget、functionTab、covenantInput、mysticInput 等）都各自创建一份相同的 QFont 对象。

**影响**: 修改字体时需要查找并更新 16 处，极易遗漏导致 UI 字体不一致。

**建议**: 提取为辅助函数 `def _make_font(size=12)` 或在方法开头创建一个共享 `QFont` 对象复用。

---

### 8. 圣约/神秘购买逻辑重复约 80 行

- **文件**: `main.py:255-293`（圣约）vs `main.py:295-333`（神秘）
- **严重程度**: 低

两个购买代码块结构完全相同，仅以下 4 处不同：

| 差异项     | 圣约购买块       | 神秘购买块       |
|-----------|-----------------|-----------------|
| 模板图片    | `covenant`      | `mystic`        |
| 日志标签    | `"聖約"`        | `"神秘"`        |
| startMode | `1`             | `2`             |
| 扣款金额    | `184000`        | `280000`        |

两个块都遵循相同的模式：`find_template` → 设 flag → 外层 retry 循环 → `double_click_at` → `wait_for` 购买按钮 → 内层 retry 循环点击购买 → 等待购买对话框消失 → 更新计数器。

**影响**: 修 bug 时容易只修改一边而遗漏另一边，导致行为不一致。

**建议**: 提取为 `_buy_bookmark(hwnd, template, label, mode, cost, found_flag, ...)` 方法，两个购买场景共用。
