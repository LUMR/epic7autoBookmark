"""配置模块 — 加载、校验、默认值生成。

向后兼容旧版 config.json：新增字段均有默认值，旧配置文件可直接使用。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

_VALID_LANGUAGES = ("zh-TW", "zh-CN", "en-US")
_VALID_CAPTURE_METHODS = ("auto", "bitblt", "mss")
_VALID_INPUT_BACKENDS = ("sendinput",)


@dataclass
class AppConfig:
    """应用全局配置。"""

    # ---- 基础设置 ----
    window_title: str = "第七史诗"
    language: str = "zh-TW"
    capture_method: str = "auto"
    input_backend: str = "sendinput"

    # ---- UI 默认值 ----
    default_money: int = 100000000
    default_stone: int = 30000
    default_covenant: int = 0
    default_mystic: int = 0
    default_stone_usage: int = 99

    # ---- 检测阈值 ----
    match_threshold_location: float = 0.9
    match_threshold_button: float = 0.85
    match_threshold_confirm: float = 0.9
    match_threshold_refresh: float = 0.8

    # ---- 时序参数 ----
    short_sleep_base: float = 1.0
    wait_timeout: float = 5.0
    wait_timeout_long: float = 8.0
    max_retry: int = 20
    swipe_fail_limit: int = 5

    @staticmethod
    def load(path: str = "config.json") -> AppConfig:
        """从 JSON 文件加载配置，缺失字段使用默认值。"""
        config_path = Path(path)
        raw: dict[str, Any] = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        return AppConfig._from_dict(raw)

    @classmethod
    def _from_dict(cls, raw: dict[str, Any]) -> AppConfig:
        """将原始字典映射到 AppConfig 字段。

        支持旧版字段名（如 e7_language → language）。
        """
        # 字段名映射：旧名 → 新名
        aliases = {
            "e7_language": "language",
            "foreground_mode": None,  # 废弃字段，忽略
        }

        kwargs: dict[str, Any] = {}
        for f in fields(cls):
            # 优先使用新字段名
            if f.name in raw:
                kwargs[f.name] = _coerce(raw[f.name], f.type)
                continue
            # 检查旧字段名映射
            for old_name, new_name in aliases.items():
                if new_name == f.name and old_name in raw:
                    kwargs[f.name] = _coerce(raw[old_name], f.type)
                    break

        return cls(**kwargs)

    def validate(self) -> list[str]:
        """校验配置，返回警告列表（空列表表示通过）。"""
        warnings: list[str] = []
        if self.language not in _VALID_LANGUAGES:
            warnings.append(
                f"不支持的语系: {self.language}，可选: {_VALID_LANGUAGES}"
            )
        if self.capture_method not in _VALID_CAPTURE_METHODS:
            warnings.append(
                f"不支持的截图方式: {self.capture_method}，可选: {_VALID_CAPTURE_METHODS}"
            )
        if self.input_backend not in _VALID_INPUT_BACKENDS:
            warnings.append(
                f"不支持的输入后端: {self.input_backend}，可选: {_VALID_INPUT_BACKENDS}"
            )
        return warnings

    def check_required_images(self, img_dir: str = "./img") -> list[str]:
        """检查必需的模板图片是否存在，返回缺失文件列表。"""
        required = [
            f"{img_dir}/covenantLocation.png",
            f"{img_dir}/mysticLocation.png",
            f"{img_dir}/buyConfirmButton-{self.language}.png",
            f"{img_dir}/refreshButton-{self.language}.png",
            f"{img_dir}/refreshYesButton-{self.language}.png",
        ]
        return [p for p in required if not Path(p).exists()]

    @property
    def ui_defaults(self) -> dict[str, str]:
        """返回 UI 输入框的默认值（字符串形式）。"""
        return {
            "money": str(self.default_money),
            "stone": str(self.default_stone),
            "covenant": str(self.default_covenant),
            "mystic": str(self.default_mystic),
            "stone_usage": str(self.default_stone_usage),
        }


def _coerce(value: Any, type_hint: str) -> Any:
    """简单的类型转换，确保 JSON 值与 dataclass 字段类型匹配。"""
    if type_hint in ("int",) and not isinstance(value, int):
        return int(value)
    if type_hint in ("float",) and not isinstance(value, float):
        return float(value)
    return value
