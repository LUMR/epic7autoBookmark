"""状态机模块 — 商店自动化的状态定义和上下文管理。

使用状态驱动替代原来的线性 while 循环，使流程更清晰、更容易调试。
"""

from __future__ import annotations

from enum import Enum, auto
from dataclasses import dataclass, field


class ShopState(Enum):
    """商店自动化的状态枚举。"""

    SCANNING = auto()        # 扫描商店列表中
    BUYING_COVENANT = auto() # 正在购买圣约书签
    BUYING_MYSTIC = auto()   # 正在购买神秘书签
    SWIPING = auto()         # 滑动商店列表
    REFRESHING = auto()      # 正在刷新商店
    DONE = auto()            # 任务完成
    ERROR = auto()           # 出错


@dataclass
class BookmarkTarget:
    """当前正在处理的书签目标（购买流程中间状态）。"""
    match_center: tuple[int, int]  # 匹配中心点 (参考分辨率坐标)
    label: str                     # "聖約" 或 "神秘"


@dataclass
class ShopContext:
    """商店自动化上下文，替代原 Worker 中的散落变量。

    集中管理所有状态，方便在状态处理器之间传递。
    """

    # ---- 窗口信息 ----
    hwnd: int

    # ---- 用户参数 ----
    mode: int  # 1=圣约, 2=神秘, 3=天空石
    expect_num: int
    money: int
    stone: int

    # ---- 状态机 ----
    state: ShopState = ShopState.SCANNING
    target: BookmarkTarget | None = None  # 当前购买目标

    # ---- 运行时标志 ----
    need_refresh: bool = False
    covenant_found: bool = False   # Bug #5 修复：购买成功后才设为 True
    mystic_found: bool = False
    swipe_fail_count: int = 0

    # ---- 统计 ----
    refresh_count: int = 0
    covenant_bought: int = 0
    mystic_bought: int = 0
    loop_count: int = 0

    # ---- 控制 ----
    _running: bool = True

    @property
    def should_continue(self) -> bool:
        """统一的循环退出条件。

        修复 Bug #4（天空石超支）：模式 3 时 expect_num 可能为负数，
        改为 expect_num >= 3 才继续。
        """
        if not self._running:
            return False
        if self.money <= 280000:
            return False
        if self.mode == 3:
            # 天空石模式：剩余数量足够再刷新一次
            return self.expect_num >= 3
        else:
            # 圣约/神秘模式：剩余次数 > 0 且有足够天空石刷新
            return self.expect_num > 0 and self.stone >= 3

    def stop(self) -> None:
        """请求优雅停止。"""
        self._running = False

    @property
    def total_stone_used(self) -> int:
        return self.refresh_count * 3

    @property
    def total_money_used(self) -> int:
        return self.covenant_bought * 184000 + self.mystic_bought * 280000
