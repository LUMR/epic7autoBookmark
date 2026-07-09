"""调试/回归检测 — 纯逻辑，无 Qt 依赖。

Inspector 封装「对一张截图计算各元素匹配值」「优先书签勾选」「截图编号保存」
「素材目录回归判定」。复用 TemplateManager / TemplateMatcher / AppConfig，
不持有可变状态（方法所需截图由外部传入），便于单元测试。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


# ---- 前缀 ↔ 模板/阈值/ROI 映射 ----

@dataclass(frozen=True)
class InspectionItem:
    """一种检测元素的映射定义。"""
    prefix: str            # 素材文件名前缀，如 "covenant"
    template_name: str     # TemplateManager.load 用的模板名
    threshold_attr: str    # AppConfig 上的阈值属性名
    roi_attr: str          # AppConfig 上的 ROI property 名
    display_name: str      # 界面显示名（繁中）


# 顺序即界面显示顺序；书签在前（pick_default 的「优先书签」依赖此顺序）。
INSPECTION_ITEMS: list[InspectionItem] = [
    InspectionItem("covenant",  "covenantLocation", "match_threshold_location", "scan_roi_tuple",   "聖約書籤"),
    InspectionItem("mystic",    "mysticLocation",   "match_threshold_location", "scan_roi_tuple",   "神秘書籤"),
    InspectionItem("buyButton", "buyButton",        "match_threshold_button",   "button_roi_tuple", "購買按鈕"),
    InspectionItem("buyConfirm","buyConfirmButton", "match_threshold_button",   "button_roi_tuple", "購買確認"),
    InspectionItem("refresh",   "refreshButton",    "match_threshold_refresh",  "button_roi_tuple", "刷新按鈕"),
    InspectionItem("refreshYes","refreshYesButton", "match_threshold_confirm",  "button_roi_tuple", "刷新確認"),
]

ITEM_DISPLAY: dict[str, str] = {it.prefix: it.display_name for it in INSPECTION_ITEMS}

BOOKMARK_PREFIXES: tuple[str, ...] = ("covenant", "mystic")

# 素材文件名格式：{prefix}_{n}.png
_INDEX_RE = re.compile(r"^(?P<prefix>.+?)_(?P<n>\d+)\.png$")


@dataclass
class ItemScore:
    """单种元素的检测结果。"""
    prefix: str
    display_name: str
    score: float | None    # 原始最高分；模板缺失为 None
    threshold: float
    passed: bool           # score is not None and score >= threshold


@dataclass
class Failure:
    """回归测试中未通过的素材。"""
    path: str
    prefix: str
    score: float
    threshold: float


@dataclass
class RegressionReport:
    """回归测试汇总。"""
    per_prefix: dict[str, tuple[int, int]]  # prefix -> (passed, total)
    failures: list[Failure]
    total: int
    passed: int


class Inspector:
    """检测/回归执行器（无 Qt 依赖、无截屏，截图由外部传入）。"""

    _RAW_THRESHOLD: float = 0.0   # 取原始最高分，不做阈值过滤

    def __init__(self, templates, matcher, config):
        self.templates = templates
        self.matcher = matcher
        self.config = config

    # ---- 检测当前画面 ----

    def inspect(self, screenshot: np.ndarray) -> list[ItemScore]:
        """对 6 种元素在各自 ROI 内计算原始最高分。模板缺失 → score=None。"""
        results: list[ItemScore] = []
        for item in INSPECTION_ITEMS:
            threshold = float(getattr(self.config, item.threshold_attr))
            roi = getattr(self.config, item.roi_attr)
            try:
                template = self.templates.load(item.template_name)
            except FileNotFoundError:
                results.append(ItemScore(item.prefix, item.display_name, None, threshold, False))
                continue
            m = self.matcher.match(screenshot, template, self._RAW_THRESHOLD, item.prefix, roi=roi)
            score = float(m.score) if m is not None else 0.0
            results.append(ItemScore(item.prefix, item.display_name, score, threshold, score >= threshold))
        return results

    def pick_default(self, scores: list[ItemScore]) -> str | None:
        """「优先书签」勾选规则：书签达标 → 取书签最高分；否则取全局最高分（并列优先书签）。全 N/A → None。"""
        bm_passed = [s for s in scores if s.prefix in BOOKMARK_PREFIXES and s.passed]
        if bm_passed:
            return max(bm_passed, key=lambda s: s.score).prefix
        valid = [s for s in scores if s.score is not None]
        if not valid:
            return None
        best_score = max(s.score for s in valid)
        tied = [s for s in valid if s.score == best_score]
        bookmark_tied = [s for s in tied if s.prefix in BOOKMARK_PREFIXES]
        if bookmark_tied:
            return bookmark_tied[0].prefix
        return tied[0].prefix

    # ---- 截图编号与保存 ----

    def next_index(self, directory: str, prefix: str) -> int:
        """扫描目录中 {prefix}_{n}.png，返回最大 n + 1（无则 1）。"""
        d = Path(directory)
        if not d.exists():
            return 1
        max_n = 0
        for p in d.iterdir():
            m = _INDEX_RE.match(p.name)
            if m and m.group("prefix") == prefix:
                max_n = max(max_n, int(m.group("n")))
        return max_n + 1

    def save_screenshot(self, screenshot: np.ndarray, directory: str, prefix: str) -> Path:
        """按 {prefix}_{n}.png 保存截图（中文路径安全）。"""
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        n = self.next_index(directory, prefix)
        path = d / f"{prefix}_{n}.png"
        ok, buf = cv2.imencode(".png", screenshot)
        if not ok:
            raise IOError(f"無法編碼 PNG: {path}")
        buf.tofile(str(path))   # np.tofile 支持中文路径（cv2.imwrite 不支持）
        return path
