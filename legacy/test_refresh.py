import aircv
import cv2
import json
import ctypes

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


def test_refresh():
    print("=" * 50)
    print("refreshButton confidence test")
    print("=" * 50)

    hwnd = find_game_window()
    if not hwnd:
        print("error: game window not found")
        return

    print(f"game window found: {hwnd}")

    template = aircv.imread(f"./img/refreshButton-{e7_language}.png")
    if template is None:
        print(f"error: cannot load template ./img/refreshButton-{e7_language}.png")
        return

    print(f"template loaded: refreshButton-{e7_language}.png")

    screenshot = capture_window(hwnd)
    print("screenshot captured")

    print("\n" + "=" * 50)
    print("testing confidence levels")
    print("=" * 50)

    confidence_levels = [0.5, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]

    for conf in confidence_levels:
        result = aircv.find_template(screenshot, template, conf)
        status = "FOUND" if result else "NOT FOUND"
        pos_info = ""
        if result:
            pos = result['result']
            pos_info = f" pos:({pos[0]:.0f}, {pos[1]:.0f})"
        print(f"confidence {conf:.2f}: {status}{pos_info}")

    cv2.imwrite("test_refresh_screenshot.png", screenshot)
    print("\nscreenshot saved: test_refresh_screenshot.png")


if __name__ == "__main__":
    test_refresh()
