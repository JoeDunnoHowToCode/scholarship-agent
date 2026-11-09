"""模型評估指令（ADR-098）：同一批來源、同一份已存的快照，讓指定的模型各抽幾次，不寫回資料庫。

用法：
  uv run python -m app.features.evaluation.run --models gemini-3.5-flash-lite gemini-3.1-flash-lite --rounds 2 --max-cost 80
  uv run python -m app.features.evaluation.run --tally 2026-11-10    讀你填好的抽查清單，補進報告

原始結果與抽查清單在 backend/data/eval/<日期>/（含各網站的原文引用，不進 git）；報告只有數字，在 docs/eval/<日期>.md。
"""

import argparse
import json
import random
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.features.costs.llm import gemini
from app.features.costs.usage import NTD_PER_USD, TAIPEI
from app.features.evaluation.metrics import (
    FIELDS,
    agreement,
    disagreements,
    grounded,
    incomplete,
    tally,
)
from app.features.scholarships.extract import (
    build_extraction,
    current_prompts,
    documents,
)
from app.features.scholarships.models import Scholarship
from app.features.scholarships.schemas import ScholarshipDraft
from app.features.sources.models import Discovery, Source, SourceStatus
from app.shared.db import SessionLocal

BACKEND = Path(__file__).resolve().parents[3]
EVAL_DIR = BACKEND / "data" / "eval"  # 原始結果與抽查清單：含原文引用，不進 git
REPORT_DIR = BACKEND.parent / "docs" / "eval"  # 報告：只有數字，進 git

SEED = 11  # 固定的亂數種子：每次挑到同一批 Erasmus 學程
ERASMUS_SAMPLE = 40


def pick_sample(non_erasmus: list[int], erasmus: list[int], n: int = ERASMUS_SAMPLE, seed: int = SEED) -> list[int]:
    """評估樣本：所有非 Erasmus 的來源，加上用固定種子挑的 n 個 Erasmus 學程。"""
    pool = sorted(set(erasmus))  # 先排序：輸入順序不同也挑到同一批
    chosen = random.Random(seed).sample(pool, min(n, len(pool)))
    return sorted(set(non_erasmus) | set(chosen))


def record_of(
    source: dict[str, Any], model: str, round_no: int, verified: ScholarshipDraft | None,
    extracted: dict[str, Any] | None, seconds: float, cost_usd: float, error: str | None,
) -> dict[str, Any]:
    """一次抽取的紀錄（格式見 metrics.py）：只留比較要用的欄位、引用與核對結果。"""
    base = {**source, "model": model, "round": round_no, "seconds": round(seconds, 2), "cost_usd": cost_usd}
    if verified is None or extracted is None:
        empty = {"deadlines": [], "nationality": "", "degrees": [], "amounts": []}
        return {**base, "ok": False, "error": error, "fields": empty, "evidence": {},
                "verification": {"nationality": None, "degrees": None, "deadlines": [], "amounts": []}, "issues": 0}
    windows = verified.windows
    fields = {
        "deadlines": sorted(
            f"{w.closes_year:04d}-{w.closes_month:02d}-{w.closes_day:02d}"
            for w in windows if w.closes_year and w.closes_month and w.closes_day
        ),
        "nationality": f"{verified.nationality_scope}:{','.join(sorted(c.upper() for c in verified.nationalities))}",
        "degrees": sorted(verified.degrees),
        "amounts": sorted(f"{a.kind}:{a.value:g}:{a.currency}:{a.period}" for a in verified.amounts),
    }
    evidence = {
        "deadlines": " / ".join(w.evidence for w in windows if w.evidence),
        "nationality": verified.nationality_evidence,
        "degrees": verified.degrees_evidence,
        "amounts": " / ".join(a.evidence for a in verified.amounts if a.evidence),
    }
    v = extracted.get("verification", {})
    verification = {
        "nationality": v.get("nationality"), "degrees": v.get("degrees"),
        "deadlines": list(v.get("deadlines", [])), "amounts": list(v.get("amounts", [])),
    }
    return {**base, "ok": True, "error": None, "fields": fields, "evidence": evidence,
            "verification": verification, "issues": len(v.get("issues", []))}


def report_markdown(results: dict[str, list[list[dict[str, Any]]]], date: str) -> str:
    """報告（只有數字，進 git）：results 是 {模型: [第 1 次的紀錄, 第 2 次的紀錄, …]}。"""
    models = list(results)
    sample = len(results[models[0]][0]) if models and results[models[0]] else 0
    rounds = max((len(r) for r in results.values()), default=0)
    lines = [
        f"# 模型評估：{date}",
        "",
        f"方法：ADR-098（替代指標＋抽查）。樣本 {sample} 個來源，每個模型抽 {rounds} 次，用同一份已存的快照、不寫回資料庫。",
        "",
        (
            "| 模型 | 國籍有根據 | 學位有根據 | 截止日有根據 | 金額有根據 | 截止日不完整 | 規則問題（平均） "
            "| 穩定度（四欄全同） | 每個來源約 | 平均秒數 | 失敗 |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for model, runs in results.items():
        records = [r for run in runs for r in run]
        ok = [r for r in records if r["ok"]]
        rates = grounded(records)
        stability = f"{agreement(runs[0], runs[1])['all']:.0%}" if len(runs) >= 2 else "—"
        cost = sum(r["cost_usd"] for r in records) / len(records) * NTD_PER_USD if records else 0.0
        seconds = sum(r["seconds"] for r in records) / len(records) if records else 0.0
        issues = sum(r["issues"] for r in ok) / len(ok) if ok else 0.0
        lines.append(
            f"| {model} | {rates['nationality']:.0%} | {rates['degrees']:.0%} | {rates['deadlines']:.0%} "
            f"| {rates['amounts']:.0%} | {incomplete(records):.0%} | {issues:.2f} | {stability} "
            f"| NT${cost:.2f} | {seconds:.1f} | {len(records) - len(ok)} |"
        )
    if len(models) >= 2:
        cross = agreement(results[models[0]][0], results[models[1]][0])
        lines += [
            "",
            f"## 兩個模型的一致率（{models[0]} 與 {models[1]}，第 1 次）",
            "",
            "| 截止日 | 國籍 | 學位 | 金額 | 四欄全同 |",
            "| --- | --- | --- | --- | --- |",
            "| " + " | ".join(f"{cross[f]:.0%}" for f in (*FIELDS, "all")) + " |",
        ]
    lines += [
        "",
        "## 說明",
        "",
        "- 有根據：原文引用撐得起抽出的值（國籍也算目錄當依據）；有根據不等於正確",
        "- 穩定度：同一個模型、同一份原文抽兩次，四個欄位都一樣的比例",
        "- PDF 的轉錄稿有快取（只看提示詞版本），兩個模型讀到的是同一份轉錄稿",
    ]
    return "\n".join(lines) + "\n"


def disagreements_markdown(items: list[dict[str, Any]], first: str, second: str) -> str:
    """抽查清單（含原文引用，不進 git）：每一筆留一行「誰對：」給你填 A、B、都對或都錯。"""
    lines = [
        "# 抽查清單",
        "",
        f"A＝{first}，B＝{second}。打開官網，看這個欄位哪一邊對，在「誰對：」後面填 A、B、都對或都錯，存檔後執行：",
        "`uv run python -m app.features.evaluation.run --tally <日期>`",
        "",
    ]
    for n, item in enumerate(items, 1):
        lines += [
            f"### {n}. {item['name']}（來源 #{item['source_id']}）",
            f"官網：{item['url']}",
            f"欄位：{item['field']}",
            f"A：{item['first']}",
            f"　引用：「{item['first_evidence'] or '沒有'}」",
            f"B：{item['second']}",
            f"　引用：「{item['second_evidence'] or '沒有'}」",
            "誰對：",
            "",
        ]
    return "\n".join(lines)


def sample_ids() -> list[int]:
    """樣本第一次挑好就存檔，之後每次評估都用同一批（改提示詞、換模型都能比）。"""
    path = EVAL_DIR / "sample.json"
    if path.exists():
        return list(json.loads(path.read_text(encoding="utf-8")))
    with SessionLocal() as session:
        rows = session.execute(
            select(Source.id, Source.discovery)
            .join(Scholarship, Scholarship.source_id == Source.id)
            .where(
                Source.enabled.is_(True), Source.status == SourceStatus.APPROVED, Source.manual_reason.is_(None),
                Source.unreachable_since.is_(None), Scholarship.duplicate_of.is_(None),
            )
        ).tuples().all()
    erasmus = [sid for sid, discovery in rows if discovery == Discovery.CATALOGUE]
    others = [sid for sid, discovery in rows if discovery != Discovery.CATALOGUE]
    ids = pick_sample(others, erasmus)
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ids), encoding="utf-8")
    return ids


def run_one(source_id: int, model: str, round_no: int) -> dict[str, Any]:
    """用指定的模型抽一個來源一次，不寫回資料庫（交易最後復原）。"""
    llm = gemini(source_id=source_id, model=model)
    started = time.monotonic()
    with SessionLocal() as session:
        source = session.get(Source, source_id)
        info = {"source_id": source_id, "name": source.name if source else "", "url": source.url if source else ""}
        try:
            snapshots = documents(session, source) if source else []
            if source is None or not snapshots:
                raise LookupError("沒有可以抽的快照")
            meta = {"snapshots": sorted(s.content_hash for s in snapshots), "prompts": current_prompts(), "model": model}
            verified, extracted = build_extraction(session, llm, source, snapshots, meta)
            return record_of(info, model, round_no, verified, extracted, time.monotonic() - started, llm.cost_usd(), None)
        # 故意接住所有錯誤：一個來源失敗算進失敗率，不讓整個評估停下來
        except Exception as error:  # noqa: BLE001
            return record_of(info, model, round_no, None, None, time.monotonic() - started, llm.cost_usd(),
                             type(error).__name__)
        finally:
            session.rollback()


def main() -> None:
    parser = argparse.ArgumentParser(description="模型評估（ADR-098）")
    parser.add_argument("--models", nargs="+", default=["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"])
    parser.add_argument("--rounds", type=int, default=2, help="每個模型抽幾次（2 次才量得到穩定度）")
    parser.add_argument("--max-cost", type=float, default=80, help="這次評估的 AI 費用上限（新台幣）")
    parser.add_argument("--limit", type=int, help="只跑樣本的前幾個（試跑用）")
    parser.add_argument("--tally", metavar="日期", help="讀這一天填好的抽查清單，補進報告")
    args = parser.parse_args()
    if args.tally:
        counts = tally((EVAL_DIR / args.tally / "disagreements.md").read_text(encoding="utf-8"))
        report = REPORT_DIR / f"{args.tally}.md"
        text = report.read_text(encoding="utf-8").split("\n## 抽查（人工）")[0].rstrip("\n")
        summary = "、".join(f"{k} {v}" for k, v in counts.items())
        report.write_text(f"{text}\n\n## 抽查（人工）\n\n兩個模型不一致的地方，人工對照官網：{summary}\n", encoding="utf-8")
        print(f"抽查：{summary}，已補進 {report}")
        return
    date = datetime.now(UTC).astimezone(TAIPEI).date().isoformat()
    ids = sample_ids()[: args.limit] if args.limit else sample_ids()
    out = EVAL_DIR / date
    out.mkdir(parents=True, exist_ok=True)
    results: dict[str, list[list[dict[str, Any]]]] = {}
    spent = 0.0
    for model in args.models:
        results[model] = []
        for round_no in range(1, args.rounds + 1):
            records = []
            for source_id in ids:
                if spent * NTD_PER_USD >= args.max_cost:
                    print(f"已達這次評估的上限 NT${args.max_cost}，停下")
                    break
                record = run_one(source_id, model, round_no)
                spent += record["cost_usd"]
                records.append(record)
                print(f"{model} 第 {round_no} 次 #{source_id} {'ok' if record['ok'] else record['error']}")
            results[model].append(records)
            (out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / f"{date}.md").write_text(report_markdown(results, date), encoding="utf-8")
    if len(args.models) >= 2:
        items = disagreements(results[args.models[0]][0], results[args.models[1]][0])
        (out / "disagreements.md").write_text(disagreements_markdown(items, args.models[0], args.models[1]), encoding="utf-8")
    print(f"樣本 {len(ids)} 個，花了約 NT${spent * NTD_PER_USD:.2f}；報告 docs/eval/{date}.md；抽查清單 {out / 'disagreements.md'}")


if __name__ == "__main__":
    main()
