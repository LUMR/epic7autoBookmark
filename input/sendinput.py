"""SendInput 输入后端 — 使用 Win32 SendInput API 发送鼠标事件。

当前唯一可用的后端。Epic Seven (Unity/OpenGL) 不响应 PostMessage 鼠标消息，
因此只能使用系统级输入。
"""

from __future__ import annotations

import ctypes
import time

import win32gui
import win32api
import win32con

from input.base import InputBackend

user32 = ctypes.windll.user32


class SendInputBackend(InputBackend):
    """通过 SendInput API 发送鼠标事件的输入后端。

    使用 win32api.mouse_event 实现（SendInput 的简化封装），
    需要管理员权限和前台窗口。
    """

    def click(self, hwnd: int, x: float, y: float) -> None:
        sx, sy = win32gui.ClientToScreen(hwnd, (int(x), int(y)))
        win32api.SetCursorPos((sx, sy))
        time.sleep(0.02)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, sx, sy, 0, 0)
        time.sleep(0.02)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, sx, sy, 0, 0)

    def double_click(self, hwnd: int, x: float, y: float) -> None:
        self.click(hwnd, x, y)
        time.sleep(0.05)
        self.click(hwnd, x, y)

    def swipe(
        self,
        hwnd: int,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        duration: float = 0.1,
    ) -> None:
        sx1, sy1 = win32gui.ClientToScreen(hwnd, (int(x1), int(y1)))
        sx2, sy2 = win32gui.ClientToScreen(hwnd, (int(x2), int(y2)))

        win32api.SetCursorPos((sx1, sy1))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, sx1, sy1, 0, 0)

        steps = 10
        step_delay = duration / steps
        for i in range(1, steps + 1):
            t = i / steps
            cx = int(sx1 + (sx2 - sx1) * t)
            cy = int(sy1 + (sy2 - sy1) * t)
            win32api.SetCursorPos((cx, cy))
            time.sleep(step_delay)

        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, sx2, sy2, 0, 0)
