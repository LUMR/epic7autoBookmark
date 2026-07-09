"""DebugWorker 截图前排期等待(_wait_game_foreground)的单元测试。

驗證 detect 在 prepare() 後、capture() 前等待遊戲視窗切到前台並重繪,
避免本工具視窗遮擋遊戲客戶區而被截入(BitBlt/MSS 讀的是螢幕像素的固有特性)。
"""
import types


def test_wait_foreground_no_handle_sleeps_fixed(monkeypatch):
    import gui

    slept = []
    monkeypatch.setattr(gui.time, "sleep", lambda d: slept.append(d))

    class Dev:
        window_handle = None

    gui._wait_game_foreground(Dev())
    assert slept == [0.5]   # 無句柄(ADB/不可用):固定等待


def test_wait_foreground_polls_until_match(monkeypatch):
    import gui

    clock = [0.0]
    monkeypatch.setattr(gui.time, "monotonic", lambda: clock[0])
    sleeps = []

    def adv(d):
        sleeps.append(d)
        clock[0] += d

    monkeypatch.setattr(gui.time, "sleep", adv)
    polls = {"n": 0}

    class FakeW32:
        @staticmethod
        def GetForegroundWindow():
            polls["n"] += 1
            return 123 if polls["n"] >= 3 else 0   # 前 2 次非遊戲,第 3 次是

    monkeypatch.setattr(gui, "win32gui", FakeW32)

    class Dev:
        window_handle = 123

    gui._wait_game_foreground(Dev(), timeout=2.0)
    assert polls["n"] >= 3                       # 輪詢到匹配才停
    assert sleeps[-1] == 0.15                    # 末尾重繪等待
    assert all(s == 0.05 for s in sleeps[:-1])   # 輪詢間隔固定


def test_wait_foreground_times_out_when_never_foreground(monkeypatch):
    import gui

    clock = [0.0]
    monkeypatch.setattr(gui.time, "monotonic", lambda: clock[0])
    sleeps = []

    def adv(d):
        sleeps.append(d)
        clock[0] += d

    monkeypatch.setattr(gui.time, "sleep", adv)
    monkeypatch.setattr(
        gui, "win32gui",
        types.SimpleNamespace(GetForegroundWindow=lambda: 0),
    )

    class Dev:
        window_handle = 123

    gui._wait_game_foreground(Dev(), timeout=1.0)
    assert sleeps[-1] == 0.15    # 超時後仍執行重繪等待再返回
    assert clock[0] >= 1.0       # 確實等到超時上限,沒有提前返回
