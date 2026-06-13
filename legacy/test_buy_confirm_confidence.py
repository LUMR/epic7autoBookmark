import aircv
import cv2
import json

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)
e7_language = config["e7_language"]

# Load screenshot and templates
screenshot = cv2.imread("buy_before_click.png")
buyButton = aircv.imread(f"./img/buyButton-{e7_language}.png")
buyConfirmButton = aircv.imread(f"./img/buyConfirmButton-{e7_language}.png")

if screenshot is None or buyButton is None or buyConfirmButton is None:
    print("Error loading images")
    exit(1)

print("=" * 50)
print("Testing buyButton (shop list)")
print("=" * 50)

for conf in [0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95]:
    result = aircv.find_template(screenshot, buyButton, conf)
    status = "FOUND" if result else "NOT FOUND"
    pos_info = ""
    if result:
        pos = result['result']
        pos_info = f" pos:({pos[0]:.0f}, {pos[1]:.0f})"
    print(f"confidence {conf:.2f}: {status}{pos_info}")

print("\n" + "=" * 50)
print("Testing buyConfirmButton (confirmation dialog)")
print("=" * 50)

for conf in [0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95]:
    result = aircv.find_template(screenshot, buyConfirmButton, conf)
    status = "FOUND" if result else "NOT FOUND"
    pos_info = ""
    if result:
        pos = result['result']
        pos_info = f" pos:({pos[0]:.0f}, {pos[1]:.0f})"
    print(f"confidence {conf:.2f}: {status}{pos_info}")
