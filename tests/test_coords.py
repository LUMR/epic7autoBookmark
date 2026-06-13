from input import base


def test_scale_identity(monkeypatch):
    monkeypatch.setattr(base.win32gui, "GetClientRect", lambda hwnd: (0, 0, 1920, 1080))
    assert base.scale_to_client(0, 960, 540) == (960.0, 540.0)


def test_scale_half_window(monkeypatch):
    # 實際視窗 960×540（參考一半），座標等比縮小一半
    monkeypatch.setattr(base.win32gui, "GetClientRect", lambda hwnd: (0, 0, 960, 540))
    assert base.scale_to_client(0, 1920, 1080) == (960.0, 540.0)
    assert base.scale_to_client(0, 960, 540) == (480.0, 270.0)
