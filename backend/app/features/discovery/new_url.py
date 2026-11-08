"""找新網址（ADR-080）：抓不到的來源，由 agent 找現在的官方網址；確認是同一個學程才換。"""

import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.costs.usage import TAIPEI
from app.features.notifications.generate import add_system_event
from app.features.pipeline.report import new_url_found_message, new_url_mismatch_message
from app.features.profiles.service import CURRENT_USER_ID
from app.features.scholarships.models import Scholarship
from app.features.sources.models import Source

# 主辦單位名稱裡太常見、不能用來辨認的字
GENERIC = frozenset({
    "the", "of", "and", "for", "in", "de", "do", "da", "university", "universities", "universidade",
    "universidad", "universita", "universite", "consortium", "european", "commission", "erasmus", "mundus",
    "programme", "program", "master", "masters", "joint", "school", "institute", "college",
})
MIN_NAME = 4  # 名稱（或縮寫）至少幾個字元才拿來比對，太短容易碰巧出現
MIN_WORDS = 3  # 用特別字比對時，名稱至少要有幾個特別字（太少容易碰巧全中）


def same_programme(names: list[str], provider: str | None, page_text: str) -> bool:
    """新網頁是不是同一個學程：找得到名稱或縮寫，而且（主辦單位有特別的字時）找得到其中一個。

    不分大小寫、忽略標點（「Claude 自行決定」第 12 點）。
    """
    page = f" {_norm(page_text)} "
    candidates = [_norm(name) for name in names]
    # 獎學金名稱常寫成「Erasmus Mundus Scholarship – 縮寫」：破折號後面那段也拿來比
    candidates += [_norm(re.split(r"\s[–—-]\s", name)[-1]) for name in names if re.search(r"\s[–—-]\s", name)]
    if not any(len(c) >= MIN_NAME and f" {c} " in page for c in candidates) and not _words_match(names, page):
        return False
    distinctive = [w for w in _norm(provider or "").split() if len(w) >= MIN_NAME and w not in GENERIC]
    # 主辦單位只有通用的字（例如 European Commission）時，只看名稱
    return not distinctive or any(f" {w} " in page for w in distinctive)


def _words_match(names: list[str], page: str) -> bool:
    """長的正式名稱常只寫後半段：名稱裡的特別字（至少 3 個，不含 Erasmus、Master 這類通用字）全部出現在網頁上也算。"""
    words = set(page.split())
    for name in names:
        distinctive = {w for w in _norm(name).split() if len(w) >= MIN_NAME and w not in GENERIC}
        if len(distinctive) >= MIN_WORDS and distinctive <= words:
            return True
    return False


def _norm(text: str) -> str:
    """小寫、標點和底線都換成空白、空白合成一格。"""
    return " ".join(re.sub(r"[\W_]+", " ", text.lower()).split())


def apply_new_url(session: Session, source: Source, new_url: str, page_text: str, now: datetime) -> bool:
    """agent 提議的新網址：同一個學程就換網址、重設抓不到的狀態並通知；否則不換、只通知。回傳有沒有換。

    呼叫的人負責 commit。
    """
    old = source.url
    replaced, reason = decide_new_url(session, source, new_url, page_text)
    key = f"new-url:{source.id}:{now.astimezone(TAIPEI).date()}"  # 同一個來源同一天只通知一次
    if replaced:
        title, lines = new_url_found_message(source.name, old, new_url)
    else:
        title, lines = new_url_mismatch_message(source.name, new_url, reason)
    add_system_event(session, CURRENT_USER_ID, key, title, lines, now)
    return replaced


def decide_new_url(session: Session, source: Source, new_url: str, page_text: str) -> tuple[bool, str]:
    """判斷並套用（不發通知）：（有沒有換, 沒換的原因）。每天的發掘工作用它，最後一天合成一則通知（ADR-093）。"""
    row = session.scalars(select(Scholarship).where(Scholarship.source_id == source.id)).first()
    names = [source.name] + ([row.name] if row is not None else [])
    # 只差結尾的 / 也算同一個網址（目錄匯入的網址常有 /，agent 提議的常沒有）
    variants = {new_url.rstrip("/"), new_url.rstrip("/") + "/"}
    taken = session.scalar(select(Source.id).where(Source.url.in_(variants), Source.id != source.id))
    if taken is not None:
        return False, f"這個網址已經是另一個來源（#{taken}）"
    if not same_programme(names, row.provider if row is not None else None, page_text):
        return False, "新網頁上找不到同一個學程的名稱或主辦單位"
    source.url = new_url
    source.fail_days, source.last_failed_on, source.unreachable_since = 0, None, None  # 回到每天檢查
    return True, ""
