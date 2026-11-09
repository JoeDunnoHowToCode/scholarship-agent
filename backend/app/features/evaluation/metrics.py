"""評估的指標（ADR-098）：都是純函式，輸入是每一次抽取的紀錄（JSON 能存的 dict）。

一筆紀錄：{"source_id", "name", "url", "model", "round", "ok", "error", "seconds", "cost_usd",
          "fields": {"deadlines": [...], "nationality": str, "degrees": [...], "amounts": [...]},
          "evidence": {欄位: 引用}, "verification": {"nationality", "degrees", "deadlines": [...], "amounts": [...]},
          "issues": 規則問題數}
"""

from typing import Any

Record = dict[str, Any]
FIELDS = ("deadlines", "nationality", "degrees", "amounts")  # 抽查也照這個順序挑
GROUNDED = frozenset({"supported", "catalogue"})  # 有根據的核對結果
ANSWERS = ("A", "B", "都對", "都錯")  # 抽查時「誰對」可以填的答案


def grounded(records: list[Record]) -> dict[str, float]:
    """各欄位的有根據率：原文引用撐得起的比例。"""
    ok = [r for r in records if r["ok"]]  # 抽取失敗的另外算失敗率，不算進來
    rates: dict[str, float] = {}
    for field in ("nationality", "degrees"):
        # 目錄當依據（ADR-053，記成 catalogue）也算有根據
        good = sum(1 for r in ok if r["verification"][field] in GROUNDED)
        rates[field] = good / len(ok) if ok else 0.0
    for field in ("deadlines", "amounts"):
        statuses = [s for r in ok for s in r["verification"][field]]
        rates[field] = sum(1 for s in statuses if s in GROUNDED) / len(statuses) if statuses else 0.0
    return rates


def incomplete(records: list[Record]) -> float:
    """截止日不完整率：抽到了但缺年份之類、沒辦法建成申請期的比例。"""
    statuses = [s for r in records if r["ok"] for s in r["verification"]["deadlines"]]
    return sum(1 for s in statuses if s == "incomplete") / len(statuses) if statuses else 0.0


def agreement(first: list[Record], second: list[Record]) -> dict[str, float]:
    """兩組結果（同一模型兩次＝穩定度；兩個模型＝一致率）每個欄位一樣的比例，只算兩邊都抽成功的來源。"""
    pairs = _pairs(first, second)
    if not pairs:
        return dict.fromkeys((*FIELDS, "all"), 0.0)
    rates = {f: sum(1 for a, b in pairs if a["fields"][f] == b["fields"][f]) / len(pairs) for f in FIELDS}
    rates["all"] = sum(1 for a, b in pairs if a["fields"] == b["fields"]) / len(pairs)
    return rates


def disagreements(first: list[Record], second: list[Record], limit: int = 10) -> list[dict[str, Any]]:
    """兩組結果不一樣的地方，給人抽查：每個來源最多一筆，最多 limit 筆；兩邊都沒抽到的不算。"""
    picked: list[dict[str, Any]] = []
    for a, b in _pairs(first, second):
        for field in FIELDS:  # 截止日最重要，排第一
            if a["fields"][field] != b["fields"][field] and (a["fields"][field] or b["fields"][field]):
                picked.append({
                    "source_id": a["source_id"], "name": a["name"], "url": a["url"], "field": field,
                    "first": a["fields"][field], "second": b["fields"][field],
                    "first_evidence": a["evidence"].get(field), "second_evidence": b["evidence"].get(field),
                })
                break  # 每個來源最多一筆，讓抽查涵蓋不同來源
        if len(picked) >= limit:
            break
    return picked


def tally(text: str) -> dict[str, int]:
    """讀抽查清單裡填好的「誰對：」，數 A、B、都對、都錯各幾筆；沒填的算未填。"""
    counts = dict.fromkeys(ANSWERS + ("未填",), 0)
    for line in text.splitlines():
        if line.startswith("誰對："):
            answer = line.removeprefix("誰對：").strip()
            counts[answer if answer in ANSWERS else "未填"] += 1
    return counts


def _pairs(first: list[Record], second: list[Record]) -> list[tuple[Record, Record]]:
    """同一個來源的兩筆紀錄，兩邊都抽取成功的才配對。"""
    by_source = {r["source_id"]: r for r in second if r["ok"]}
    return [(a, by_source[a["source_id"]]) for a in first if a["ok"] and a["source_id"] in by_source]
