"""截取刷新前后画面，计算像素差异，找出最佳 before_threshold"""
import json
import time
import cv2
import numpy as np
import win32gui
import win32ui
import win32con
import ctypes

# DPI awareness
ctypes.windll.user32.SetProcessDPIAware()

REF_WIDTH = 1920
REF_HEIGHT = 1080

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)
window_title = config.get("window_title", "Epic Seven")


def find_window():
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
        img = np.asarray(bytearray(bmp_str), dtype="uint8")
        img = img.reshape((bmp_info["bmHeight"], bmp_info["bmWidth"], 4))
        img = img[:, :, :3]
        if client_width != REF_WIDTH or client_height != REF_HEIGHT:
            img = cv2.resize(img, (REF_WIDTH, REF_HEIGHT))
        return img
    finally:
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(0, desktop_dc)


hwnd = find_window()
if not hwnd:
    print("找不到遊戲視窗")
    exit(1)
print(f"遊戲視窗: {hwnd}")

rect = win32gui.GetWindowRect(hwnd)
print(f"視窗位置: {rect}")
client_rect = win32gui.GetClientRect(hwnd)
print(f"客戶區大小: {client_rect[2]}x{client_rect[3]}")

# 阶段1: 截取刷新前画面
print("\n請打開秘密商店，停留在商店畫面")
input("準備好後按 Enter 截取「刷新前」畫面...")
before = capture_window(hwnd)
cv2.imwrite("debug_before.png", before)
print("已儲存 debug_before.png")

# 阶段2: 手动刷新后截取
print("\n請現在手動刷新商店，等待商店內容完全載入")
input("載入完成後按 Enter 截取「刷新後」畫面...")
after = capture_window(hwnd)
cv2.imwrite("debug_after.png", after)
print("已儲存 debug_after.png")

# 阶段3: 再截一张静态画面（模拟未刷新）
time.sleep(0.5)
static = capture_window(hwnd)

# 计算差异
diff_before_after = cv2.absdiff(before, after).mean()
diff_static = cv2.absdiff(after, static).mean()

print(f"\n===== 結果 =====")
print(f"刷新前 vs 刷新後 (整體均值): {diff_before_after:.4f}")
print(f"刷新後 vs 靜態幀 (整體均值):  {diff_static:.4f}")

# 分区域计算
h, w = before.shape[:2]
regions = {
    "左上 (商品區)": (0, 0, w//2, h//2),
    "右上": (w//2, 0, w, h//2),
    "左下": (0, h//2, w//2, h),
    "右下 (按鈕區)": (w//2, h//2, w, h),
}

print(f"\n分區差異 (刷新前 vs 刷新後):")
for name, (x1, y1, x2, y2) in regions.items():
    d = cv2.absdiff(before[y1:y2, x1:x2], after[y1:y2, x1:x2]).mean()
    print(f"  {name}: {d:.4f}")

# 直方图分析
print(f"\n像素差異分佈:")
diff_map = cv2.absdiff(before, after).mean(axis=2)
print(f"  差異=0 的像素比例:   {(diff_map == 0).sum() / diff_map.size * 100:.1f}%")
print(f"  差異<5 的像素比例:   {(diff_map < 5).sum() / diff_map.size * 100:.1f}%")
print(f"  差異<10 的像素比例:  {(diff_map < 10).sum() / diff_map.size * 100:.1f}%")
print(f"  差異<20 的像素比例:  {(diff_map < 20).sum() / diff_map.size * 100:.1f}%")
print(f"  差異>=20 的像素比例: {(diff_map >= 20).sum() / diff_map.size * 100:.1f}%")
print(f"  最大差異值: {diff_map.max():.1f}")

# 推荐
print(f"\n===== 建議 =====")
print(f"連續幀判斷 (loading動畫是否停止) threshold 應 >= {diff_static * 2:.1f}")
recommended = max(diff_before_after * 0.5, 0.3)
print(f"刷新前後判斷 before_threshold 應 <= {recommended:.2f}")
print(f"建議 before_threshold = {recommended:.2f}")
