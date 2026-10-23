"""評分指令（第 6 天；第 7 天改成只算適配度。spec「評分」、ADR-040、046、053、054、055、059、060）。

用法：uv run python -m app.features.matching.score [--max-cost NT$]

每個（獎學金 × 類別）：
1. 硬性條件由程式判斷（國籍、學位），每次都重算，不花錢；時間也會算出來，但只給網頁顯示，不影響分數
2. 適配度：領域契合由 AI 評（送出去的內容沒變就沿用上次的分數），想去的國家由程式比對；沒填的不評
3. 總分 = min(上限, 依權重加總)；不符合上限 20、待確認上限 80
"""

import argparse
import hashlib
import sys
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.llm.base import StructuredLLM
from app.core.llm.gemini import GeminiLLM, LLMError, MissingApiKeyError
from app.features.matching import checks
from app.features.matching.models import Match
from app.features.matching.scoring import CheckResult, apply_caps
from app.features.profiles.models import Profile
from app.features.profiles.service import CURRENT_USER_ID, get_profile
from app.features.scholarships import countries
from app.features.scholarships.cycles import is_stale
from app.features.scholarships.models import Cycle, Scholarship, ScholarshipStatus
from app.shared.db import SessionLocal
from app.shared.settings import settings

PROMPT_VERSION = "score-4"  # 改提示詞就要改版本號

PROMPT = """你是留學獎學金顧問。依下面的資料，評估這位申請人和這個獎學金的這個類別在領域上有多契合：
獎學金或學程的領域，和申請人的目前科系、想讀的領域有多契合。
給 0–10 分，分數越高越契合，附一句繁體中文理由。只根據資料判斷，不要推測；
資料沒寫或無法判斷時給 5 分，並在理由說明。

獎學金：
{scholarship}

申請人：
{applicant}
"""

# 給人看的中文名稱
STATUS_NAMES = {"open": "開放中", "upcoming": "即將開放", "closed": "已截止", "estimated": "預估"}
SCOPE_NAMES = {"all": "不限國籍", "listed": "只限列出的國家", "excluded": "列出的國家以外都可以", "unclear": "原文沒寫"}
DEGREE_NAMES = {"bachelor": "學士", "master": "碩士", "phd": "博士"}


class SubScore(BaseModel):
    # 一定要是數字：空白會被加權總分跳過、其他項放大，等於把「不知道」當成「和其他項一樣好」
    score: float = Field(ge=0, le=10, description="0–10 分；資料沒寫或無法判斷時給 5 分")
    reason: str = Field(description="一句繁體中文理由")


def cycle_infos(cycles: list[Cycle]) -> list[checks.CycleInfo]:
    return [
        checks.CycleInfo(
            status=c.status,
            nationality_scope=c.nationality_scope,
            nationalities=tuple(c.nationalities),
            funding=c.funding,
            verified=c.verification == "supported",  # 預估的申請期沒有驗證結果，狀態是 estimated
        )
        for c in cycles
    ]


def possible_cycles(cycles: list[Cycle], user: str) -> list[Cycle]:
    """還有機會申請的申請期（和 checks.still_possible 同一套規則），依截止時間排序。"""
    infos = cycle_infos(cycles)  # 只建一次：下面用「是不是同一個物件」來對應回原本的申請期
    keep = {id(info) for info in checks.still_possible(infos, user)}
    return sorted((c for c, info in zip(cycles, infos, strict=True) if id(info) in keep), key=lambda c: c.closes_at)


def nationality_fit(cycle: Cycle, user: str) -> CheckResult:
    """這一期的國籍範圍適不適用你；國家清單不明時是待確認。"""
    return checks.nationality_check(user, cycle.nationality_scope, list(cycle.nationalities))


def describe_cycle(cycle: Cycle) -> str:
    """例如「2027-01-15（開放中，截止日未核對）Partner countries」；日期用原文的時區。"""
    local = cycle.closes_at.astimezone(ZoneInfo(cycle.timezone)) if cycle.timezone and not cycle.timezone_assumed else cycle.closes_at
    notes = [STATUS_NAMES.get(cycle.status, cycle.status)]
    if cycle.estimated and cycle.evidence:
        notes.append(cycle.evidence)  # 例如「依 2022 年的日期推估」（ADR-058）
    if not cycle.estimated and cycle.verification != "supported":
        notes.append("截止日未核對")
    return f"{local:%Y-%m-%d}（{'，'.join(notes)}）{cycle.label or ''}".strip()


def time_reason(row: Scholarship, user: str, possible: list[Cycle]) -> str:
    """時間條件的一句原因，和 checks.time_check 的判斷一致。"""
    if not row.cycles:
        # 抽到了截止日，但年月日不齊全或年份是 AI 自己補的，不建申請期（docs/day-04.md「Claude 自行決定」第 4 點）
        return "原文有截止日，但年份或日期不完整，無法確認" if row.extracted.get("windows") else "原文沒有截止日"
    if not possible:
        funded = [c for c in row.cycles if c.funding in ("scholarship", "any")]
        if not funded:
            return "只找到自費生的申請期，沒有獎學金的截止日"
        latest = max((c.closes_at for c in row.cycles if not c.estimated), default=None)
        if latest is not None and row.status == ScholarshipStatus.ARCHIVED and is_stale(latest, datetime.now(UTC).date()):
            return f"資料過舊：官網最新資訊是 {latest:%Y} 年，可能已停辦（ADR-058）"
        if any(nationality_fit(c, user) != "fail" for c in funded):
            return "適用你的申請期都已截止"
        return "有截止日，但都不適用你的國籍"
    # 先列確定適用你、開放中或即將開放、截止日核對過的那一期（time_check 判符合靠的就是它）
    sure = [
        c for c in possible
        if c.status in ("open", "upcoming") and c.verification == "supported" and nationality_fit(c, user) == "pass"
    ]
    shown = (sure or possible)[0]
    note = "；這一期的國家清單不明" if nationality_fit(shown, user) == "unclear" else ""
    return f"適用你的截止日：{describe_cycle(shown)}{note}"


def hard_checks(
    profile: Profile, row: Scholarship, category: dict[str, Any], possible: list[Cycle]
) -> dict[str, tuple[CheckResult, str]]:
    """國籍、學位、時間：（結果, 一句原因），全部由程式判斷。國籍、學位會壓總分上限；時間只給網頁顯示（ADR-059）。"""
    basis = row.extracted.get("verification", {}).get("nationality")
    scope = SCOPE_NAMES.get(row.nationality_scope, row.nationality_scope)
    if row.nationalities:
        scope += f"（{len(row.nationalities)} 國）"
    elif row.nationality_scope in ("listed", "excluded"):
        scope += "（沒有列出國家）"  # 例如原文只寫「African Union 會員國」
    nationality = checks.nationality_check(profile.nationality, row.nationality_scope, list(row.nationalities))
    nationality_reason = f"國籍資格：{scope}" + ("；依據：EACEA 目錄頁" if basis == "catalogue" else "")

    degrees = [str(d) for d in category.get("degrees") or []]
    conditions = category.get("degree_conditions") or None
    degree = checks.degree_check(profile.target_degree, degrees, conditions)
    names = "、".join(DEGREE_NAMES.get(d, d) for d in degrees) or "原文沒寫"
    degree_reason = f"可讀學位：{names}" + (f"；條件：{conditions}" if conditions else "")

    time = checks.time_check(cycle_infos(list(row.cycles)), profile.nationality)
    return {
        "nationality": (nationality, nationality_reason),
        "degree": (degree, degree_reason),
        "time": (time, time_reason(row, profile.nationality, possible)),
    }


def scholarship_text(row: Scholarship, category: dict[str, Any]) -> str:
    """送給 AI 的獎學金資料：只放判斷領域需要的（ADR-059），也不含申請人的國籍。"""
    return "\n".join(
        [
            f"名稱：{row.name}",
            f"領域：{', '.join(row.fields) or '沒寫'}",
            f"類別：{category.get('name')}",
        ]
    )


def country_part(profile: Profile, row: Scholarship, category: dict[str, Any]) -> dict[str, Any]:
    """想去的國家（ADR-060）：程式比對類別的留學國家（類別沒寫就用獎學金的），不送給 AI。"""
    destinations = [str(c) for c in category.get("countries") or []] or list(row.countries)
    score = checks.country_score(list(profile.target_countries), destinations)
    if score is None:
        reason = "沒有填想去的國家，不評"
    elif not destinations:
        reason = "原文沒寫留學國家"
    else:
        names = "、".join(countries.display_name(c) for c in destinations)
        reason = f"留學國家：{names}；" + ("有你想去的國家" if score == 10 else "沒有你想去的國家")
    return {"score": score, "reason": reason}


def applicant_text(profile: Profile) -> str:
    """送給 AI 的個人資料只有科系與想讀的領域（ADR-055）。"""
    major = profile.current_major or "沒有填"
    fields = ", ".join(profile.target_fields) or "沒有填"
    return f"目前科系：{major}\n想讀的領域：{fields}"


def score_all(session: Session, llm: StructuredLLM, model_id: str, profile: Profile, max_cost: float | None) -> dict[str, int]:
    counts = {"scored": 0, "reused": 0, "computed": 0, "no_ai": 0, "cap20": 0, "cap80": 0, "full": 0, "failed": 0}
    rows = session.scalars(
        select(Scholarship)
        .where(Scholarship.duplicate_of.is_(None), Scholarship.source_id.is_not(None))
        .options(selectinload(Scholarship.cycles))
        .order_by(Scholarship.id)
    ).all()
    existing = {
        (m.scholarship_id, m.category_name): m
        for m in session.scalars(select(Match).where(Match.user_id == profile.user_id))
    }
    kept: set[tuple[int, str]] = set()
    no_field = not profile.current_major and not profile.target_fields
    for row in rows:
        possible = possible_cycles(list(row.cycles), profile.nationality)
        for category in row.extracted.get("categories", []):
            key = (row.id, str(category["name"]))
            kept.add(key)
            results = hard_checks(profile, row, category, possible)
            scholarship, applicant = scholarship_text(row, category), applicant_text(profile)
            input_hash = hashlib.sha256(f"{model_id}\n{PROMPT_VERSION}\n{scholarship}\n{applicant}".encode()).hexdigest()
            match = existing.get(key)
            if no_field:
                # 沒填科系與領域：不評領域契合，也就不用呼叫 AI（ADR-060）
                field: dict[str, Any] = {"score": None, "reason": "沒有填科系與想讀的領域，不評領域契合"}
                counts["no_ai"] += 1
            elif match is not None and match.input_hash == input_hash:
                field = match.sub_scores["field"]  # 送出去的內容沒變：沿用，不呼叫 AI
                counts["reused"] += 1
            else:
                if max_cost and isinstance(llm, GeminiLLM) and llm.cost_usd() * 32 > max_cost:
                    print(f"已超過這次的費用上限 NT${max_cost}，停下")
                    return counts
                try:
                    answer = llm.extract(PROMPT.format(scholarship=scholarship, applicant=applicant), SubScore)
                except LLMError as error:
                    counts["failed"] += 1
                    print(f"failed     {row.id} {row.name[:40]}｜{category['name']}：{error}")
                    continue
                field = answer.model_dump()
                counts["computed"] += 1
            sub_scores = {"field": field, "country": country_part(profile, row, category)}
            # 只有國籍、學位會壓總分上限；時間只留給網頁顯示（ADR-059）
            capped = {name: results[name][0] for name in ("nationality", "degree")}
            verdicts = list(capped.values())
            total = apply_caps(
                checks.weighted_total({k: v["score"] for k, v in sub_scores.items()}), verdicts
            )
            cap = 20 if "fail" in verdicts else 80 if "unclear" in verdicts else None
            counts["cap20" if cap == 20 else "cap80" if cap == 80 else "full"] += 1
            values = {
                "total": total,
                "cap": cap,
                "checks": {name: {"result": r, "reason": why} for name, (r, why) in results.items()},
                "sub_scores": sub_scores,
                "unclear": [name for name, r in capped.items() if r == "unclear"],
                "failed": [name for name, r in capped.items() if r == "fail"],
                "model": model_id,
                "prompt_version": PROMPT_VERSION,
                "profile_version": profile.version,
                "input_hash": input_hash,
                "computed_at": datetime.now(UTC),
            }
            if match is None:
                session.add(Match(user_id=profile.user_id, scholarship_id=row.id, category_name=key[1], **values))
            else:
                for name, value in values.items():
                    setattr(match, name, value)  # JSONB 欄位整個重新指定（CLAUDE.md 程式規範）
            counts["scored"] += 1
        session.commit()  # 每筆獎學金各自一個交易：中途停下，已評好的不會不見
    # 已經不存在的類別（重抽後改名或刪掉）：刪掉它們的評分
    stale = [m.id for key, m in existing.items() if key not in kept]
    if stale:
        session.execute(delete(Match).where(Match.id.in_(stale)))
        session.commit()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="依個人資料替每個（獎學金 × 類別）評分")
    parser.add_argument("--max-cost", type=float, help="這次執行的 AI 費用上限（新台幣）")
    args = parser.parse_args()
    try:
        llm = GeminiLLM(settings.llm_model, settings.google_api_key, settings.llm_requests_per_minute)
    except MissingApiKeyError as error:
        sys.exit(str(error))
    # expire_on_commit=False：commit 之後不要把已讀進來的資料標成過期，
    # 否則下一筆獎學金一碰到欄位就會重新查一次資料庫（每筆多兩個查詢，就是 N+1）
    with SessionLocal(expire_on_commit=False) as session:
        profile = get_profile(session, CURRENT_USER_ID)
        if profile is None:
            sys.exit("還沒有個人資料：先執行 uv run python -m app.features.profiles.set --nationality TW --degree master")
        counts = score_all(session, llm, settings.llm_model, profile, args.max_cost)
    print(
        f"評分 {counts['scored']} 筆（領域契合：AI 沿用 {counts['reused']}、重算 {counts['computed']}、"
        f"失敗 {counts['failed']}、沒填不評 {counts['no_ai']}）；"
        f"上限 20：{counts['cap20']}、上限 80：{counts['cap80']}、沒有上限：{counts['full']}"
    )
    print(llm.usage_line())


if __name__ == "__main__":
    main()
