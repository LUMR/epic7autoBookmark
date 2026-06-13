import aircv
import cv2
import json
import ctypes
import time

ctypes.windll.user32.SetProcessDPIAware()
import win32gui

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)
e7_language = config["e7_language"]
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


def capture_window(hwnd):
    import win32ui
    import win32con
    from numpy import asarray

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


def test_buy_confirm():
    print("=" * 50)
    print("buyConfirm button test")
    print("=" * 50)
    print("Steps:")
    print("1. Make sure the game shows the buy button")
    print("2. This script will capture screenshots before and after clicking")
    print("=" * 50)

    hwnd = find_game_window()
    if not hwnd:
        print("error: game window not found")
        return

    print(f"game window found: {hwnd}")

    template = aircv.imread(f"./img/buyButton-{e7_language}.png")
    if template is None:
        print(f"error: cannot load template ./img/buyButton-{e7_language}.png")
        return

    print("Step 1: Capturing screenshot before clicking buy button...")
    screenshot1 = capture_window(hwnd)

    # Find buy button position
    result = aircv.find_template(screenshot1, template, 0.85)
    if not result:
        print("error: buy button not found in screenshot")
        return

    buy_pos = result['result']
    print(f"buy button found at: ({buy_pos[0]:.0f}, {buy_pos[1]:.0f})")

    # Save first screenshot
    cv2.imwrite("buy_before_click.png", screenshot1)
    print("Saved: buy_before_click.png")

    # Click the buy button
    print("\nStep 2: Clicking buy button...")
    client_rect = win32gui.GetClientRect(hwnd)
    sx = int(buy_pos[0] * client_rect[2] / REF_WIDTH)
    sy = int(buy_pos[1] * client_rect[3] / REF_HEIGHT)

    # Use PostMessage to click
    import win32con
    lparam = (sy << 16) | (sx & 0xFFFF)
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
    time.sleep(0.05)
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)

    print("Clicked! Waiting 1 second...")
    time.sleep(1)

    # Capture screenshot after clicking
    print("\nStep 3: Capturing screenshot after clicking buy button...")
    screenshot2 = capture_window(hwnd)
    cv2.imwrite("buy_after_click.png", screenshot2)
    print("Saved: buy_after_click.png")

    # Check if buy button still exists
    result2 = aircv.find_template(screenshot2, template, 0.85)
    if result2:
        print("Buy button still visible after clicking")
        print(f"Position: ({result2['result'][0]:.0f}, {result2['result'][1]:.0f})")
    else:
        print("Buy button disappeared after clicking (good!)")

    print("\n" + "=" * 50)
    print("Done! Check the screenshots:")
    print("- buy_before_click.png (before clicking)")
    print("- buy_after_click.png (after clicking)")
    print("=" * 50)


if __name__ == "__main__":
    test_buy_confirm()
