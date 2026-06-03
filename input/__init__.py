"""输入模块 — 统一的多后端鼠标输入接口。"""

from input.base import InputBackend
from input.sendinput import SendInputBackend


def create_backend(method: str = "sendinput") -> InputBackend:
    """创建输入后端实例。

    Args:
        method: 输入方式。目前仅支持 "sendinput"。

    Returns:
        InputBackend 实例。

    Raises:
        ValueError: 不支持的输入方式。
    """
    if method == "sendinput":
        return SendInputBackend()
    raise ValueError(f"不支持的输入后端: {method}")
