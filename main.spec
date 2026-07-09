# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = ['win32api', 'win32gui', 'win32ui', 'win32con']

# cv2 / mss 基于 ctypes 动态加载,需 collect_all 确保动态库完整收集
for pkg in ('cv2', 'mss'):
    tmp = collect_all(pkg)
    datas += tmp[0]; binaries += tmp[1]; hiddenimports += tmp[2]

# PyQt6 仅用 QtCore/QtGui/QtWidgets。不用 collect_all(否则暴力打包 Qt3D/WebEngine/QML
# 等未用模块,致 exe 膨胀至 140MB+);改由 PyInstaller 按 import 智能收集,并显式排除未用大模块。
qt_excludes = [
    'PyQt6.Qt3DCore', 'PyQt6.Qt3DRender', 'PyQt6.Qt3DInput', 'PyQt6.Qt3DLogic',
    'PyQt6.Qt3DAnimation', 'PyQt6.Qt3DExtras',
    'PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebEngineQuick',
    'PyQt6.QtWebChannel', 'PyQt6.QtWebSockets',
    'PyQt6.QtQml', 'PyQt6.QtQuick', 'PyQt6.QtQuick3D', 'PyQt6.QtQuickWidgets',
    'PyQt6.QtQuickControls2', 'PyQt6.QtQmlWorkerScript',
    'PyQt6.QtMultimedia', 'PyQt6.QtMultimediaWidgets',
    'PyQt6.QtSql', 'PyQt6.QtPdf', 'PyQt6.QtPdfWidgets',
    'PyQt6.QtCharts', 'PyQt6.QtDataVisualization',
    'PyQt6.QtBluetooth', 'PyQt6.QtPositioning', 'PyQt6.QtLocation',
    'PyQt6.QtSensors', 'PyQt6.QtSerialPort', 'PyQt6.QtNfc',
    'PyQt6.QtScxml', 'PyQt6.QtRemoteObjects', 'PyQt6.QtSpatialAudio',
    'PyQt6.QtTextToSpeech', 'PyQt6.QtXmlPatterns',
]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=qt_excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['main.ico'],
)
