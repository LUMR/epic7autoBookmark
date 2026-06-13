"""bitblt 冒煙測試 — 不依賴遊戲視窗的結構性驗證。

完整截圖驗證需真實視窗，留給手動驗證（見計畫 Task 6 Step 2）。
"""
import capture.bitblt as bitblt


def test_close_all_empty_sessions():
    """close_all 在無會話時應安全無副作用。"""
    bitblt._sessions.clear()
    bitblt.close_all()
    assert bitblt._sessions == {}


def test_reusable_capture_close_uninitialized():
    """未初始化的會話呼叫 _close 不應崩（所有資源為 None）。"""
    sess = bitblt._ReusableCapture(12345)
    sess._close()
    assert sess._bitmap is None
    assert sess._save_dc is None
