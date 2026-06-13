"""测试各种 PostMessage/SendMessage 点击方式"""
import ctypes
import json
import time
import numpy as np
from numpy import asarray
import cv2
import aircv

import win32gui
import win32ui
import win32con

ctypes.windll.user32.SetProcessDPIAware()

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)
window_title = config.get("window_title", "Epic Seven")
e7_language = config.get("e7_language", "zh-TW")

REF_WIDTH = 1920
REF_HEIGHT = 1080
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
MK_LBUTTON = 0x0001
user32 = ctypes.windll.user32


def make_lparam(x, y):
    return (y << 16) | (x & 0xFFFF)


def find_game_window():
    candidates = []
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and window_title in win32gui.GetWindowText(hwnd):
            rect = win32gui.GetClientRect(hwnd)
            area = rect[2] * rect[3]
            candidates.append((area, hwnd))
    win32gui.EnumWindows(callback, None)
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def capture_window(hwnd):
    client_left, client_top = win32gui.ClientToScreen(hwnd, (0, 0))
    client_rect = win32gui.GetClientRect(hwnd)
    client_width = client_rect[2]
    client_height = client_rect[3]
    desktop_dc = win32gui.GetDC(0)
    mfc_dc = win32ui.CreateDCFromHandle(desktop_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(mfc_dc, client_width, client_height)
    save_dc.SelectObject(bitmap)
    try:
        save_dc.BitBlt(
            (0, 0), (client_width, client_height),
            mfc_dc, (client_left, client_top),
            win32con.SRCCOPY
        )
        bmp_info = bitmap.GetInfo()
        bmp_str = bitmap.GetBitmapBits(True)
        img = asarray(bytearray(bmp_str), dtype="uint8")
        img = img.reshape((bmp_info["bmHeight"], bmp_info["bmWidth"], 4))
        img = img[:, :, :3]
        if client_width != REF_WIDTH or client_height != REF_HEIGHT:
            img = cv2.resize(img, (REF_WIDTH, REF_HEIGHT))
        return img
    finally:
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(0, desktop_dc)
        win32gui.DeleteObject(bitmap.GetHandle())


def check_confirm_dialog(img):
    refresh_yes_btn = cv2.imread(f"./img/refreshYesButton-{e7_language}.png")
    return aircv.find_template(img, refresh_yes_btn, 0.8)


hwnd = find_game_window()
if not hwnd:
    print(f"找不到窗口")
    exit(1)

client_rect = win32gui.GetClientRect(hwnd)
cw, ch = client_rect[2], client_rect[3]
scale_x = cw / REF_WIDTH
scale_y = ch / REF_HEIGHT
print(f"客户区: {cw}x{ch}")

# 找刷新按钮
refresh_btn = cv2.imread(f"./img/refreshButton-{e7_language}.png")
img = capture_window(hwnd)
cv2.imwrite("test_click_before.png", img)
refresh_pos = aircv.find_template(img, refresh_btn, 0.8)
if not refresh_pos:
    print("未找到刷新按钮！")
    exit(1)

rx, ry = refresh_pos["result"]
# 实际坐标
ax = int(rx * scale_x)
ay = int(ry * scale_y)
print(f"刷新按钮: ref=({rx:.0f}, {ry:.0f}) actual=({ax}, {ay})")

# 方式1: 简单 PostMessage（当前代码的方式）
def test_click(name, click_fn):
    print(f"\n--- {name} ---")
    img_before = capture_window(hwnd)
    click_fn(hwnd, ax, ay)
    time.sleep(1.5)
    img_after = capture_window(hwnd)
    result = check_confirm_dialog(img_after)
    if result:
        print(f"  [OK] 有效！确认按钮 at ({result['result'][0]:.0f}, {result['result'][1]:.0f})")
        # 关闭对话框 - 按 ESC 键
        time.sleep(0.5)
        # 点取消区域（点对话框外的左上角）
        user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, make_lparam(100, 100))
        time.sleep(0.02)
        user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, make_lparam(100, 100))
        time.sleep(1.5)
        return True
    else:
        print(f"  [FAIL] 无效")
        return False


# 方式1: 简单 PostMessage
def simple_postmsg(hwnd, x, y):
    lp = make_lparam(x, y)
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lp)
    time.sleep(0.02)
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lp)

# 方式2: 简单 SendMessage
def simple_sendmsg(hwnd, x, y):
    lp = make_lparam(x, y)
    user32.SendMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lp)
    time.sleep(0.02)
    user32.SendMessageW(hwnd, WM_LBUTTONUP, 0, lp)

# 方式3: 完整消息序列 (MOVE + DOWN + UP)
def full_postmsg(hwnd, x, y):
    lp = make_lparam(x, y)
    user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lp)
    time.sleep(0.01)
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lp)
    time.sleep(0.05)
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lp)

# 方式4: 完整 SendMessage 序列
def full_sendmsg(hwnd, x, y):
    lp = make_lparam(x, y)
    user32.SendMessageW(hwnd, WM_MOUSEMOVE, 0, lp)
    time.sleep(0.01)
    user32.SendMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lp)
    time.sleep(0.05)
    user32.SendMessageW(hwnd, WM_LBUTTONUP, 0, lp)

# 方式5: 用 SendInput 模拟（通过 SendMessage 转发）
def sendinput_click(hwnd, x, y):
    """SendInput 是系统级输入，需要屏幕坐标"""
    # 这种方式其实是 real_click，但我们没有管理员权限
    # 跳过
    pass

# 方式6: PostMessage 到父窗口
def postmsg_ancestor(hwnd, x, y):
    """发送给祖先窗口"""
    ancestor = user32.GetAncestor(hwnd, 2)  # GA_ROOT
    if ancestor == hwnd:
        print("  (已是顶层窗口，跳过)")
        return
    lp = make_lparam(x, y)
    user32.PostMessageW(ancestor, WM_MOUSEMOVE, 0, lp)
    time.sleep(0.01)
    user32.PostMessageW(ancestor, WM_LBUTTONDOWN, MK_LBUTTON, lp)
    time.sleep(0.05)
    user32.PostMessageW(ancestor, WM_LBUTTONUP, 0, lp)

results = {}
for name, fn in [
    ("1. PostMessage 简单", simple_postmsg),
    ("2. SendMessage 简单", simple_sendmsg),
    ("3. PostMessage 完整(MOVE+DOWN+UP)", full_postmsg),
    ("4. SendMessage 完整(MOVE+DOWN+UP)", full_sendmsg),
    ("5. PostMessage 祖先窗口", postmsg_ancestor),
]:
    results[name] = test_click(name, fn)

print("\n===== 结果汇总 =====")
for name, ok in results.items():
    print(f"  {'[OK]' if ok else '[FAIL]'} {name}")

if not any(results.values()):
    print("\n所有 PostMessage/SendMessage 方式均无效。")
    print("Epic Seven (Unity/OpenGL) 不响应 PostMessage 鼠标消息。")
    print("解决方案: 使用 SendInput 系统级输入，但需要管理员权限。")
