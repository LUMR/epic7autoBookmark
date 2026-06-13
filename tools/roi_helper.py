"""ROI 框選輔助 — 截取遊戲視窗後互動式框選，輸出 config.json 用的 [x,y,w,h]。

用法：python tools/roi_helper.py
框選兩個 ROI（書籤掃描區、按鈕區）後列印結果，按 q 結束。
"""
import cv2
from worker import find_game_window
from capture import capture_window
from config import AppConfig

config = AppConfig.load()
hwnd = find_game_window(config.window_title)
if not hwnd:
    raise SystemExit("找不到遊戲視窗")

img = capture_window(hwnd, config.capture_method)
clone = img.copy()
rects = {"scan_roi": [], "button_roi": []}
state = {"current": "scan_roi", "drawing": False, "ix": 0, "iy": 0}


def on_mouse(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        state["drawing"] = True
        state["ix"], state["iy"] = x, y
    elif event == cv2.EVENT_MOUSEMOVE and state["drawing"]:
        preview = clone.copy()
        cv2.rectangle(preview, (state["ix"], state["iy"]), (x, y), (0, 255, 0), 2)
        cv2.imshow("roi", preview)
    elif event == cv2.EVENT_LBUTTONUP:
        state["drawing"] = False
        rects[state["current"]] = [
            min(state["ix"], x), min(state["iy"], y),
            abs(x - state["ix"]), abs(y - state["iy"]),
        ]
        print(f'{state["current"]} = {rects[state["current"]]}')
        state["current"] = "button_roi" if state["current"] == "scan_roi" else "done"


cv2.namedWindow("roi")
cv2.setMouseCallback("roi", on_mouse)
print("框選【書籤掃描區】→ 再框選【按鈕區】→ 按 q 結束")
while True:
    cv2.imshow("roi", clone)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break
cv2.destroyAllWindows()

print("\n請將以下加入 config.json：")
print(f'  "scan_roi": {rects["scan_roi"]},')
print(f'  "button_roi": {rects["button_roi"]},')
