"""模板管理模块 — 多语言模板加载与缓存。

加载 img/ 目录下的模板图片，支持语言后缀回退：
优先加载 name-{lang}.png，不存在时回退到 name.png。
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


class TemplateManager:
    """模板图片管理器。"""

    def __init__(self, language: str, img_dir: str = "./img"):
        self.language = language
        self.img_dir = Path(img_dir)
        self._cache: dict[str, np.ndarray] = {}

    def load(self, name: str) -> np.ndarray:
        """加载模板图片，带缓存。

        加载顺序：
        1. {name}-{language}.png（语言特定版本）
        2. {name}.png（通用版本）

        Args:
            name: 模板文件名（不含扩展名）。

        Returns:
            BGR 格式的 numpy ndarray。

        Raises:
            FileNotFoundError: 模板文件不存在。
        """
        if name in self._cache:
            return self._cache[name]

        # 尝试语言特定版本
        lang_path = self.img_dir / f"{name}-{self.language}.png"
        if lang_path.exists():
            img = self._load_image(lang_path)
            self._cache[name] = img
            return img

        # 回退到通用版本
        generic_path = self.img_dir / f"{name}.png"
        if generic_path.exists():
            img = self._load_image(generic_path)
            self._cache[name] = img
            return img

        raise FileNotFoundError(
            f"模板图片不存在: {lang_path} 或 {generic_path}"
        )

    @staticmethod
    def _load_image(path: Path) -> np.ndarray:
        """读取图片文件，兼容含中文的路径。"""
        # cv2.imread 不支持含中文的路径，使用 imdecode 替代
        data = np.fromfile(str(path), dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"无法读取图片: {path}")
        return img

    # ---- 便捷属性：常用模板 ----

    @property
    def covenant(self) -> np.ndarray:
        """圣约书签位置模板。"""
        return self.load("covenantLocation")

    @property
    def mystic(self) -> np.ndarray:
        """神秘书签位置模板。"""
        return self.load("mysticLocation")

    @property
    def buy_confirm(self) -> np.ndarray:
        """购买确认按钮模板（语言特定）。"""
        return self.load("buyConfirmButton")

    @property
    def refresh_button(self) -> np.ndarray:
        """刷新按钮模板（语言特定）。"""
        return self.load("refreshButton")

    @property
    def refresh_yes(self) -> np.ndarray:
        """刷新确认按钮模板（语言特定）。"""
        return self.load("refreshYesButton")
