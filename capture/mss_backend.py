"""MSS 截图后端 — 使用 mss 库截取窗口区域。

作为 BitBlt 的备选方案，支持高 DPI 和多显示器场景。
"""

from __future__ import annotations

import cv2
import numpy as np
import win32gui

from capture import REF_WIDTH, REF_HEIGHT, CaptureError

try:
    import mss
    import mss.base
except ImportError:
    mss = None  # type: ignore[assignment]


def capture_mss(hwnd: int) -> np.ndarray:
    """使用 MSS 截取窗口客户区。

    Args:
        hwnd: 目标窗口句柄。

    Returns:
        BGR 格式的 numpy ndarray，尺寸 (REF_HEIGHT, REF_WIDTH, 3)。

    Raises:
        CaptureError: mss 未安装或截图失败。
    """
    if mss is None:
        raise CaptureError("mss 库未安装，请执行 pip install mss")

    # 获取窗口客户区的屏幕坐标
    left, top = win32gui.ClientToScreen(hwnd, (0, 0))
    rect = win32gui.GetClientRect(hwnd)
    width = rect[2]
    height = rect[3]

    monitor = {
        "left": left,
        "top": top,
        "width": width,
        "height": height,
    }

    try:
        with mss.mss() as sct:
            shot = sct.grab(monitor)
            img = np.array(shot, dtype=np.uint8)
            # mss 返回 BGRA，转为 BGR
            img = img[:, :, :3]
            if width != REF_WIDTH or height != REF_HEIGHT:
                img = cv2.resize(img, (REF_WIDTH, REF_HEIGHT))
            return img
    except Exception as e:
        raise CaptureError(f"MSS 截图失败: {e}") from e
