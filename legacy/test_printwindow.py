"""测试 PrintWindow vs BitBlt 截图效果"""
import ctypes
import json
import time
import numpy as np
from numpy import asarray
import cv2

import win32gui
import win32ui
import win32con

ctypes.windll.user32.SetProcessDPIAware()

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)
window_title = config.get("window_title", "Epic Seven")
REF_WIDTH = 1920
REF_HEIGHT = 1080

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

def _bitmap_to_img(bitmap, client_width, client_height):
    bmp_info = bitmap.GetInfo()
    bmp_str = bitmap.GetBitmapBits(True)
    img = asarray(bytearray(bmp_str), dtype="uint8")
    img = img.reshape((bmp_info["bmHeight"], bmp_info["bmWidth"], 4))
    img = img[:, :, :3]
    if client_width != REF_WIDTH or client_height != REF_HEIGHT:
        img = cv2.resize(img, (REF_WIDTH, REF_HEIGHT))
    return img

def capture_bitblt(hwnd):
    """当前方法: BitBlt 从屏幕 DC 复制"""
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
        img = _bitmap_to_img(bitmap, client_width, client_height)
        return img
    finally:
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(0, desktop_dc)
        win32gui.DeleteObject(bitmap.GetHandle())

def capture_printwindow(hwnd):
    """PrintWindow 方法: 后台截图，支持遮挡"""
    client_rect = win32gui.GetClientRect(hwnd)
    client_width = client_rect[2]
    client_height = client_rect[3]

    # 计算窗口尺寸和客户区偏移（用于裁剪标题栏）
    window_rect = win32gui.GetWindowRect(hwnd)
    client_origin = win32gui.ClientToScreen(hwnd, (0, 0))
    offset_x = client_origin[0] - window_rect[0]
    offset_y = client_origin[1] - window_rect[1]
    window_width = window_rect[2] - window_rect[0]
    window_height = window_rect[3] - window_rect[1]

    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(mfc_dc, window_width, window_height)
    save_dc.SelectObject(bitmap)
    try:
        result = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)
        img = _bitmap_to_img(bitmap, client_width, client_height)
        # 裁剪到客户区
        img_full = _bitmap_to_img(bitmap, window_width, window_height)
        return result, img_full, offset_x, offset_y, client_width, client_height
    finally:
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)
        win32gui.DeleteObject(bitmap.GetHandle())

# ===== 测试 =====
hwnd = find_game_window()
if not hwnd:
    print(f"找不到窗口标题包含 '{window_title}' 的窗口")
    exit(1)

print(f"找到窗口: hwnd={hwnd}, 标题='{win32gui.GetWindowText(hwnd)}'")
window_rect = win32gui.GetWindowRect(hwnd)
client_rect = win32gui.GetClientRect(hwnd)
print(f"窗口矩形: {window_rect}")
print(f"客户区: {client_rect}")

# BitBlt 截图
print("\n--- BitBlt 截图 ---")
t0 = time.time()
img_bitblt = capture_bitblt(hwnd)
t1 = time.time()
mean_bb = img_bitblt.mean()
cv2.imwrite("debug_bitblt.png", img_bitblt)
print(f"耗时: {(t1-t0)*1000:.0f}ms")
print(f"像素均值: {mean_bb:.1f} (0=全黑, 128=正常)")
print(f"已保存: debug_bitblt.png")

# PrintWindow 截图
print("\n--- PrintWindow 截图 ---")
t0 = time.time()
result, img_full, ox, oy, cw, ch = capture_printwindow(hwnd)
t1 = time.time()
mean_pw_full = img_full.mean()
# 裁剪到客户区
img_printwindow = img_full[oy:oy+ch, ox:ox+cw]
if cw != REF_WIDTH or ch != REF_HEIGHT:
    img_printwindow = cv2.resize(img_printwindow, (REF_WIDTH, REF_HEIGHT))
mean_pw = img_printwindow.mean()
cv2.imwrite("debug_printwindow_full.png", img_full)
cv2.imwrite("debug_printwindow.png", img_printwindow)
print(f"PrintWindow 返回值: {result} (非0=成功)")
print(f"裁剪偏移: offset=({ox},{oy}), 客户区=({cw}x{ch})")
print(f"耗时: {(t1-t0)*1000:.0f}ms")
print(f"像素均值(全窗口): {mean_pw_full:.1f}")
print(f"像素均值(客户区): {mean_pw:.1f}")
print(f"已保存: debug_printwindow_full.png, debug_printwindow.png")

# 结论
print("\n===== 结论 =====")
if mean_pw < 5:
    print("PrintWindow 返回黑屏 → 不适用于此游戏，无法后台截图")
elif abs(mean_pw - mean_bb) < 10:
    print("PrintWindow 截图正常，与 BitBlt 结果一致 → 可以支持遮挡窗口")
else:
    print(f"PrintWindow 截图有内容但与 BitBlt 差异较大 (均值差={abs(mean_pw - mean_bb):.1f})")
    print("可能部分有效，建议人工检查 debug_printwindow.png")
