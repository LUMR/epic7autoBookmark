import aircv
import cv2
import json
import ctypes

# DPI awareness
ctypes.windll.user32.SetProcessDPIAware()

import win32gui

# Load config
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


def test_confidence():
    print("=" * 50)
    print("确认按钮置信度测试")
    print("=" * 50)

    # Find game window
    hwnd = find_game_window()
    if not hwnd:
        print("错误: 找不到游戏窗口")
        return

    print(f"游戏窗口已找到: {hwnd}")

    # Load template
    template = aircv.imread(f"./img/refreshYesButton-{e7_language}.png")
    if template is None:
        print(f"错误: 无法加载模板图片 ./img/refreshYesButton-{e7_language}.png")
        return

    print(f"模板图片已加载: refreshYesButton-{e7_language}.png")

    # Capture screenshot
    screenshot = capture_window(hwnd)
    print("截图已捕获")

    # Test different confidence levels
    print("\n" + "=" * 50)
    print("测试不同置信度阈值")
    print("=" * 50)

    confidence_levels = [0.5, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]

    results = []
    for conf in confidence_levels:
        result = aircv.find_template(screenshot, template, conf)
        status = "找到" if result else "未找到"
        pos_info = ""
        if result:
            pos = result['result']
            pos_info = f" 位置:({pos[0]:.0f}, {pos[1]:.0f})"
        print(f"置信度 {conf:.2f}: {status}{pos_info}")
        results.append((conf, result))

    # Find optimal confidence
    print("\n" + "=" * 50)
    print("分析结果")
    print("=" * 50)

    found_confidences = [conf for conf, result in results if result is not None]
    not_found_confidences = [conf for conf, result in results if result is None]

    if found_confidences:
        print(f"找到匹配的置信度: {found_confidences}")
        optimal = min(found_confidences)
        print(f"建议的最低置信度: {optimal}")
        print(f"当前代码使用的置信度: 0.65")
        if 0.65 in found_confidences:
            print("[OK] 当前设置可以识别确认按钮")
        else:
            print("[FAIL] 当前设置可能无法识别确认按钮")
    else:
        print("未找到任何匹配，可能需要更换截图")

    # Save test screenshot for reference
    cv2.imwrite("test_screenshot.png", screenshot)
    print("\n测试截图已保存: test_screenshot.png")


if __name__ == "__main__":
    test_confidence()
