"""從簡章文字抽出獎學金資料，存進 scholarships 表（第 1 天的最小版本）。

用法：uv run python -m app.features.scholarships.extract <簡章文字檔> [--url 官方網址]
"""

import argparse
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.core.llm.base import StructuredLLM
from app.core.llm.gemini import GeminiLLM, MissingApiKeyError
from app.features.scholarships.models import Scholarship, TaiwanEligibility
from app.shared.db import SessionLocal
from app.shared.settings import settings

# 提示詞版本：改了提示詞就要改這個號碼（之後會是快取鍵的一部分，ADR-013）
PROMPT_VERSION = "extract-1"

PROMPT = """你是留學獎學金資料的抽取助手。只根據下面的簡章原文填寫欄位：
- 原文沒寫的欄位留空，不要推測
- 原文沒提到台灣籍能不能申請時，taiwan_eligibility 一律填 unclear
- evidence 欄位要逐字引用原文的句子

簡章原文：
{text}
"""


class ScholarshipDraft(BaseModel):
    """模型抽出的初稿；第 3 天會加上驗證者檢查。"""

    name: str = Field(description="獎學金的原文名稱")
    provider: str | None = Field(description="提供單位；原文沒寫就留空")
    countries: list[str] = Field(description="可以去留學的國家，用英文國名")
    degrees: list[Literal["bachelor", "master", "phd"]] = Field(description="適用的學位")
    taiwan_eligibility: Literal["yes", "no", "unclear"] = Field(
        description="台灣籍能否申請；原文沒提到台灣就填 unclear"
    )
    taiwan_evidence: str | None = Field(
        description="支持 taiwan_eligibility 的原文句子，逐字引用"
    )
    deadline: str | None = Field(description="申請截止日，格式 YYYY-MM-DD；原文沒寫就留空")
    deadline_evidence: str | None = Field(description="支持截止日的原文句子，逐字引用")


def extract_draft(llm: StructuredLLM, text: str) -> ScholarshipDraft:
    # 只依賴插座（StructuredLLM），不管背後是哪一家模型
    return llm.extract(PROMPT.format(text=text), ScholarshipDraft)


def save_draft(draft: ScholarshipDraft, official_url: str | None) -> int:
    """把初稿存成一列，回傳資料庫發的 id。"""
    with SessionLocal() as session, session.begin():
        row = Scholarship(
            name=draft.name,
            provider=draft.provider,
            countries=draft.countries,
            degrees=draft.degrees,
            taiwan_eligibility=TaiwanEligibility(draft.taiwan_eligibility),
            official_url=official_url,
            # 完整初稿（含截止日與引用）存進 JSONB；截止日欄位要等第 4 天的 cycles 表
            extracted=draft.model_dump(mode="json"),
        )
        session.add(row)
        session.flush()  # 先送出 INSERT，才拿得到 id；離開 with 時才 commit
        return row.id


def main() -> None:
    parser = argparse.ArgumentParser(description="從簡章文字抽出獎學金資料並存檔")
    parser.add_argument("path", type=Path, help="簡章文字檔")
    parser.add_argument("--url", help="官方網址")
    args = parser.parse_args()

    try:
        llm = GeminiLLM(settings.llm_model, settings.google_api_key)
    except MissingApiKeyError as error:
        sys.exit(str(error))  # 印出提示並以錯誤碼 1 結束

    draft = extract_draft(llm, args.path.read_text(encoding="utf-8"))
    scholarship_id = save_draft(draft, args.url)
    print(f"已存進 scholarships，id={scholarship_id}")
    print(draft.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
