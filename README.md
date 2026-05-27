# epic7autoBookmark

第七史詩刷商店的小工具（Windows 版）

![image](https://github.com/steven010116/epic7autoBookmark/assets/24381832/526e78b9-df97-4500-9758-55f514eed883)

## 一、環境

0. Windows 10/11
1. 第七史詩 Windows 版
   i. 解析度設定為 1920x1080
2. Python 3.9+（如自行編譯）
3. config.json
   i. `window_title` 填遊戲視窗標題（預設 `"Epic Seven"`，打開遊戲後可在工作管理員確認）
   ii. `e7_language` 填遊戲內的語系（繁中: zh-TW, 簡中: zh-CN, 英文: en-US）
   iii. `foreground_mode` 設為 `true` 會佔用滑鼠（較可靠），`false` 為背景模式不佔用滑鼠（預設）

## 二、使用方式

### 方式一：直接執行 EXE

1. 綠色按鈕 Code > Download ZIP 整包下載後解壓縮，放在同一個資料夾下，路徑建議為英數避免問題
2. 確認 `config.json` 內的參數正確
3. 開啟遊戲，進到秘密商店
4. 執行 `main.exe`（在 `dist/` 目錄下）
5. 選擇條件並輸入目標次數，按下開始

### 方式二：從原始碼執行

1. 安裝依賴：`pip install -r requirements.txt`
2. 執行：`python main.py`

### 自行打包 EXE

1. 安裝 PyInstaller：`pip install pyinstaller`
2. 打包：`pyinstaller -F -w -i main.ico --hidden-import=win32api --hidden-import=win32gui --hidden-import=win32ui --hidden-import=win32con --collect-all PyQt6 main.py`
`python -m PyInstaller main.spec`
3. 產出的 `dist/main.exe` 需與 `config.json` 和 `img/` 放在同一目錄下才能執行：
   ```
   資料夾/
   ├── main.exe
   ├── config.json
   └── img/
       ├── covenantLocation.png
       ├── mysticLocation.png
       ├── buyButton-zh-TW.png
       └── ...
   ```

## 三、運作原理

- 透過 Windows API（PrintWindow）背景截取遊戲視窗畫面
- 使用圖像辨識（OpenCV 模板匹配）定位書籤和按鈕位置
- 透過 PostMessage 發送點擊訊息，不佔用滑鼠，遊戲視窗可被遮擋
- 若 PostMessage 點擊無效，可在 config.json 設 `foreground_mode: true` 降級為真實滑鼠操作

## 四、特別感謝

Raven9527 - 自動點擊派遣功能
