"""截图模块 — 统一的多后端窗口捕获接口。"""

# 参考分辨率，放在导入之前避免循环导入（子模块会 from capture import REF_WIDTH）
REF_WIDTH = 1920
REF_HEIGHT = 1080


class CaptureError(Exception):
    """截图失败时抛出的异常。"""


from capture.bitblt import capture_bitblt
from capture.mss_backend import capture_mss


def capture_window(hwnd: int, method: str = "auto") -> "numpy.ndarray":
    """截取游戏窗口客户区，返回 BGR ndarray (REF_WIDTH × REF_HEIGHT)。

    Args:
        hwnd: 目标窗口句柄。
        method: 截图方式。
            "auto"   — 先尝试 BitBlt，失败后回退到 MSS。
            "bitblt" — 仅使用 BitBlt（GDI）。
            "mss"    — 仅使用 MSS。

    Returns:
        BGR 格式的 numpy ndarray，尺寸 (REF_HEIGHT, REF_WIDTH, 3)。

    Raises:
        CaptureError: 所有可用后端均失败时抛出。
    """
    if method == "auto":
        try:
            return capture_bitblt(hwnd)
        except CaptureError:
            return capture_mss(hwnd)
    elif method == "bitblt":
        return capture_bitblt(hwnd)
    elif method == "mss":
        return capture_mss(hwnd)
    else:
        raise ValueError(f"不支持的截图方式: {method}")
