"""通知的插座（ADR-005、063）：功能模組只交出結構化的通知，排版交給各管道的轉接頭（第一版只有 Telegram）。"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Notification:
    """一則通知：類型、標題、內容的每一行、一個連結；怎麼排版由轉接頭決定。"""

    kind: str  # new_scholarship、new_cycle、deadline、change、system、digest（摘要）
    title: str
    lines: tuple[str, ...] = ()
    url: str | None = None


class Notifier(Protocol):
    """通知管道的插座：送出一則通知；送不出去就丟出例外，讓呼叫的人決定要不要重試。"""

    def send(self, notification: Notification) -> None: ...
