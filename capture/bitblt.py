"""BitBlt 截图后端 — 使用 GDI BitBlt 复制窗口客户区像素。

修复了原版 main.py 中的 GDI 资源泄漏问题（Bug #3）：
使用 context manager 确保所有 GDI 对象在所有路径下释放。
"""

from __future__ import annotations

import win32gui
import win32ui
import win32con
import cv2
import numpy as np

from capture import REF_WIDTH, REF_HEIGHT, CaptureError


class _GDIContext:
    """GDI 资源管理器，确保 DC 和 Bitmap 在所有路径下正确释放。

    用法::

        with _GDIContext(hwnd) as ctx:
            ctx.bitblt()
            img = ctx.to_array()
    """

    def __init__(self, hwnd: int):
        self.hwnd = hwnd
        self._desktop_dc: int | None = None
        self._mfc_dc: win32ui.CDC | None = None
        self._save_dc: win32ui.CDC | None = None
        self._bitmap: win32ui.CBitmap | None = None

    def __enter__(self) -> _GDIContext:
        client_left, client_top = win32gui.ClientToScreen(self.hwnd, (0, 0))
        client_rect = win32gui.GetClientRect(self.hwnd)
        self._client_width = client_rect[2]
        self._client_height = client_rect[3]
        self._client_left = client_left
        self._client_top = client_top

        self._desktop_dc = win32gui.GetDC(0)
        self._mfc_dc = win32ui.CreateDCFromHandle(self._desktop_dc)
        self._save_dc = self._mfc_dc.CreateCompatibleDC()

        self._bitmap = win32ui.CreateBitmap()
        self._bitmap.CreateCompatibleBitmap(
            self._mfc_dc, self._client_width, self._client_height
        )
        self._save_dc.SelectObject(self._bitmap)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """确保所有 GDI 资源释放。"""
        try:
            if self._save_dc is not None:
                self._save_dc.DeleteDC()
        except Exception:
            pass
        try:
            if self._mfc_dc is not None:
                self._mfc_dc.DeleteDC()
        except Exception:
            pass
        try:
            if self._desktop_dc is not None:
                win32gui.ReleaseDC(0, self._desktop_dc)
        except Exception:
            pass
        try:
            if self._bitmap is not None:
                win32gui.DeleteObject(self._bitmap.GetHandle())
        except Exception:
            pass

    def bitblt(self) -> None:
        """执行 BitBlt 复制窗口客户区。"""
        if self._save_dc is None:
            raise CaptureError("GDI context not initialized")
        try:
            self._save_dc.BitBlt(
                (0, 0),
                (self._client_width, self._client_height),
                self._mfc_dc,
                (self._client_left, self._client_top),
                win32con.SRCCOPY,
            )
        except Exception as e:
            raise CaptureError(f"BitBlt 失败: {e}") from e

    def to_array(self) -> np.ndarray:
        """将 Bitmap 转换为 BGR ndarray 并缩放到参考分辨率。"""
        if self._bitmap is None:
            raise CaptureError("GDI context not initialized")

        bmp_info = self._bitmap.GetInfo()
        bmp_str = self._bitmap.GetBitmapBits(True)
        img = np.asarray(bytearray(bmp_str), dtype="uint8")
        img = img.reshape((bmp_info["bmHeight"], bmp_info["bmWidth"], 4))
        img = img[:, :, :3]  # 去除 alpha 通道

        if self._client_width != REF_WIDTH or self._client_height != REF_HEIGHT:
            img = cv2.resize(img, (REF_WIDTH, REF_HEIGHT))

        return img


def capture_bitblt(hwnd: int) -> np.ndarray:
    """使用 BitBlt 截取窗口客户区。

    Args:
        hwnd: 目标窗口句柄。

    Returns:
        BGR 格式的 numpy ndarray，尺寸 (REF_HEIGHT, REF_WIDTH, 3)。

    Raises:
        CaptureError: 截图失败。
    """
    with _GDIContext(hwnd) as ctx:
        ctx.bitblt()
        return ctx.to_array()
