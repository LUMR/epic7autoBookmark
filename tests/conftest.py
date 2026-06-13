"""pytest 共享 fixture。"""
import sys
from pathlib import Path

# 讓測試能 import 專案根目錄的模組
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
