"""BitBlt 截图后端 — GDI 會話復用版本。

模塊級按 hwnd 快取可復用會話，避免每次截圖重建 DC/Bitmap；
視窗尺寸變化時自動重建。任務結束時呼叫 close_all() 釋放。

修復原版的 GDI 資源管理（Bug #3）：所有物件在 _close() 的所有路徑下釋放。
"""

from __future__ import annotations

import win32gui
import win32ui
import win32con
import cv2
import numpy as np

from capture import REF_WIDTH, REF_HEIGHT, CaptureError


class _ReusableCapture:
    """可復用的 GDI 截圖會話。

    用法：透過模塊級 capture_bitblt() 取得，毋須直接實例化。
    """

    def __init__(self, hwnd: int):
        self.hwnd = hwnd
        self._desktop_dc = None
        self._mfc_dc = None
        self._save_dc = None
        self._bitmap = None
        self._w = 0
        self._h = 0
        self._client_left = 0
        self._client_top = 0

    def _ensure(self) -> None:
        """確認 DC/Bitmap 就緒；視窗尺寸變化時重建。"""
        client_left, client_top = win32gui.ClientToScreen(self.hwnd, (0, 0))
        rect = win32gui.GetClientRect(self.hwnd)
        w, h = rect[2], rect[3]
        if self._bitmap is not None and self._w == w and self._h == h:
            # 尺寸不變，只更新視窗位置（視窗可能被拖動）
            self._client_left = client_left
            self._client_top = client_top
            return
        # 首次或尺寸變化：重建
        self._close()
        self._client_left, self._client_top = client_left, client_top
        self._w, self._h = w, h
        self._desktop_dc = win32gui.GetDC(0)
        self._mfc_dc = win32ui.CreateDCFromHandle(self._desktop_dc)
        self._save_dc = self._mfc_dc.CreateCompatibleDC()
        self._bitmap = win32ui.CreateBitmap()
        self._bitmap.CreateCompatibleBitmap(self._mfc_dc, w, h)
        self._save_dc.SelectObject(self._bitmap)

    def grab(self) -> np.ndarray:
        """截圖並回傳 BGR ndarray (REF_HEIGHT × REF_WIDTH × 3)。"""
        self._ensure()
        try:
            self._save_dc.BitBlt(
                (0, 0), (self._w, self._h),
                self._mfc_dc, (self._client_left, self._client_top),
                win32con.SRCCOPY,
            )
            bmp_str = self._bitmap.GetBitmapBits(True)
            info = self._bitmap.GetInfo()
            img = np.asarray(bytearray(bmp_str), dtype="uint8")
            img = img.reshape((info["bmHeight"], info["bmWidth"], 4))[:, :, :3]
            if self._w != REF_WIDTH or self._h != REF_HEIGHT:
                img = cv2.resize(img, (REF_WIDTH, REF_HEIGHT))
            return img
        except Exception as e:
            raise CaptureError(f"BitBlt 失敗: {e}") from e

    def _close(self) -> None:
        """釋放所有 GDI 資源；未初始化時安全無副作用。"""
        for closer in (
            lambda: self._save_dc.DeleteDC() if self._save_dc else None,
            lambda: self._mfc_dc.DeleteDC() if self._mfc_dc else None,
            lambda: win32gui.ReleaseDC(0, self._desktop_dc) if self._desktop_dc else None,
            lambda: win32gui.DeleteObject(self._bitmap.GetHandle()) if self._bitmap else None,
        ):
            try:
                closer()
            except Exception:
                pass
        self._save_dc = None
        self._mfc_dc = None
        self._desktop_dc = None
        self._bitmap = None
        self._w = 0
        self._h = 0


# 模塊級會話快取：hwnd → _ReusableCapture
_sessions: dict[int, _ReusableCapture] = {}


def capture_bitblt(hwnd: int) -> np.ndarray:
    """使用 BitBlt 截取視窗客戶區（會話復用）。

    Args:
        hwnd: 目標視窗句柄。

    Returns:
        BGR 格式的 numpy ndarray，尺寸 (REF_HEIGHT, REF_WIDTH, 3)。

    Raises:
        CaptureError: 截圖失敗（會丟棄快取的會話，下次重建）。
    """
    sess = _sessions.get(hwnd)
    if sess is None:
        sess = _ReusableCapture(hwnd)
        _sessions[hwnd] = sess
    try:
        return sess.grab()
    except CaptureError:
        # 失敗時丟棄會話，下次重建
        sess._close()
        _sessions.pop(hwnd, None)
        raise


def close_all() -> None:
    """釋放所有快取的 GDI 會話（任務結束或程式退出時呼叫）。"""
    for sess in list(_sessions.values()):
        sess._close()
    _sessions.clear()
