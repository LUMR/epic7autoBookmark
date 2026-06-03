"""模板匹配引擎 — 使用 OpenCV 实现多尺度模板匹配，替代 aircv。

支持：
- 多尺度匹配（可配置缩放因子列表）
- ROI 区域限制（可选，加速匹配）
- 统一的 MatchResult 数据类
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class MatchResult:
    """模板匹配结果。"""

    name: str
    score: float
    box: tuple[int, int, int, int]  # (x, y, w, h)

    @property
    def center(self) -> tuple[int, int]:
        """匹配区域中心点坐标。"""
        x, y, w, h = self.box
        return (x + w // 2, y + h // 2)


# 默认单尺度（保持与原 aircv 行为一致）
DEFAULT_SCALE_FACTORS = [1.0]

# 多尺度（覆盖 ±10% 分辨率偏差）
MULTI_SCALE_FACTORS = [0.9, 0.95, 1.0, 1.05, 1.1]


class TemplateMatcher:
    """多尺度模板匹配器。"""

    def __init__(self, scale_factors: list[float] | None = None):
        """初始化匹配器。

        Args:
            scale_factors: 模板缩放因子列表。None 使用默认单尺度。
        """
        self.scale_factors = scale_factors or DEFAULT_SCALE_FACTORS

    def match(
        self,
        image: np.ndarray,
        template: np.ndarray,
        threshold: float = 0.8,
        name: str = "",
        roi: tuple[int, int, int, int] | None = None,
    ) -> MatchResult | None:
        """在 image 中搜索 template。

        Args:
            image: 目标截图 (BGR)。
            template: 模板图片 (BGR)。
            threshold: 匹配置信度阈值 (0-1)。
            name: 结果名称（用于日志）。
            roi: 搜索区域 (x, y, w, h)，None 表示全图搜索。

        Returns:
            MatchResult 或 None（未找到）。
        """
        best_result: MatchResult | None = None

        for scale in self.scale_factors:
            # 缩放模板
            if scale != 1.0:
                h, w = template.shape[:2]
                new_w, new_h = int(w * scale), int(h * scale)
                if new_w < 1 or new_h < 1:
                    continue
                scaled_template = cv2.resize(template, (new_w, new_h))
            else:
                scaled_template = template

            # 裁剪搜索区域
            search_area = image
            offset_x, offset_y = 0, 0
            if roi is not None:
                rx, ry, rw, rh = roi
                search_area = image[ry : ry + rh, rx : rx + rw]
                offset_x, offset_y = rx, ry

            # 模板尺寸不能大于搜索区域
            th, tw = scaled_template.shape[:2]
            sh, sw = search_area.shape[:2]
            if th > sh or tw > sw:
                continue

            result = self._match_single(search_area, scaled_template)
            if result is None:
                continue

            score, max_loc = result
            if score < threshold:
                continue

            # 检查是否是最佳匹配
            if best_result is None or score > best_result.score:
                best_result = MatchResult(
                    name=name,
                    score=score,
                    box=(
                        max_loc[0] + offset_x,
                        max_loc[1] + offset_y,
                        tw,
                        th,
                    ),
                )

        return best_result

    def _match_single(
        self, image: np.ndarray, template: np.ndarray
    ) -> tuple[float, tuple[int, int]] | None:
        """单次模板匹配。

        Returns:
            (score, max_loc) 或 None。
        """
        if image.size == 0 or template.size == 0:
            return None

        result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        return (float(max_val), max_loc)
