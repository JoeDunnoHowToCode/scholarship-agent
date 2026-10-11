"""抽取用的 Pydantic schema（ADR-011、031、034、040）。

欄位的 description 會連同 schema 一起送給模型，等於是填表說明。
可能缺的欄位允許 null 或 unclear；關鍵欄位附逐字引用的 evidence，之後由驗證者核對原文。
"""

from typing import Literal

from pydantic import BaseModel, Field

Degree = Literal["bachelor", "master", "phd"]
TaiwanAnswer = Literal["yes", "no", "unclear"]
# 原文怎麼描述國籍資格；「台灣能不能申請」的規則之後可能改，先把原文的說法存下來
NationalityScope = Literal["worldwide", "listed_countries", "taiwan_specific", "unclear"]
# 文件類型代號（docs/day-03.md「Claude 自行決定」第 13 點）
DocType = Literal[
    "cv",
    "motivation_letter",
    "recommendation_letter",
    "transcript",
    "degree_certificate",
    "language_test",
    "passport",
    "research_proposal",
    "portfolio",
    "admission_letter",
    "financial_proof",
    "application_form",
    "other",
]


class CategoryDraft(BaseModel):
    """一個名額類別，例如教育部的「北歐國家」（ADR-040）。"""

    name: str = Field(description="類別名稱；整個獎學金只有一種時，填獎學金名稱")
    quota: int | None = Field(description="名額，只填數字；原文沒寫就留空")
    degrees: list[Degree] = Field(description="這個類別可以讀的學位")
    countries: list[str] = Field(description="這個類別可以去的國家，用英文國名")
    amount: str | None = Field(description="這個類別的補助金額，照原文寫")
    eligibility: str | None = Field(description="這個類別特有的資格條件")
    evidence: str | None = Field(description="支持名額與學位的原文句子，逐字引用")


class RequirementDraft(BaseModel):
    """申請要交的一份文件。"""

    doc_type: DocType = Field(description="文件類型代號；對不上就填 other")
    details: str | None = Field(description="具體要求，例如字數、格式、語言、要不要認證")
    required: bool | None = Field(description="必要填 true，選填填 false，原文沒說就留空")
    count: int | None = Field(description="份數，例如推薦信 2 封；原文沒說就留空")
    category: str | None = Field(description="只有某個類別要交時填類別名稱；所有人都要交就留空")
    evidence: str | None = Field(description="要求這份文件的原文句子，逐字引用")


class ProgramFacts(BaseModel):
    """整個獎學金共用的欄位。"""

    provider: str | None = Field(description="提供單位；原文沒寫就留空")
    countries: list[str] = Field(description="可以去留學的國家，用英文國名")
    degrees: list[Degree] = Field(description="適用的學位")
    degrees_evidence: str | None = Field(description="支持學位的原文句子，逐字引用")
    fields: list[str] = Field(description="適用的領域，用英文；不限領域就留空清單")
    coverage: str | None = Field(description="補助內容，例如學費、生活費、機票")
    amount: str | None = Field(description="補助金額，照原文寫，例如「每月 EUR 1,400」")
    taiwan_eligibility: TaiwanAnswer = Field(
        description="台灣籍能否申請；原文沒有明確提到台灣就填 unclear，不要推測"
    )
    taiwan_evidence: str | None = Field(description="提到台灣的原文句子，逐字引用")
    nationality_scope: NationalityScope = Field(
        description=(
            "原文怎麼描述國籍資格：開放所有國籍填 worldwide；列出特定國家填 listed_countries；"
            "專給台灣人填 taiwan_specific；沒寫填 unclear"
        )
    )
    nationality_evidence: str | None = Field(description="描述國籍資格的原文句子，逐字引用")
    taiwan_conditions: str | None = Field(description="台灣申請人特有的條件")
    language_requirements: str | None = Field(description="語言要求，例如 IELTS 6.5")
    other_eligibility: str | None = Field(description="其他資格條件，例如學歷、工作年資、年齡")
    requires_admission: bool | None = Field(
        description="申請獎學金前是否必須先拿到學校的入學許可；原文沒說就留空"
    )
    intake: str | None = Field(description="入學年度，例如 2027/28")
    deadline: str | None = Field(description="申請截止日，格式 YYYY-MM-DD；原文沒寫就留空")
    deadline_timezone: str | None = Field(description="截止時間的時區，例如 CET；原文沒寫就留空")
    deadline_evidence: str | None = Field(description="寫著截止日的原文句子，逐字引用")


class ScholarshipDraft(ProgramFacts):
    """一個獎學金的完整抽取結果：一般網頁整份抽，或長文件合併後的結果。"""

    name: str = Field(description="獎學金或學程的原文名稱")
    name_zh: str | None = Field(description="中文名稱；原文不是中文就翻譯")
    categories: list[CategoryDraft] = Field(description="名額類別；只有一種也要填一個")
    requirements: list[RequirementDraft] = Field(description="申請要交的文件")


class Outline(BaseModel):
    """長文件第一輪：只列名稱與類別清單（輸出短）。"""

    name: str = Field(description="獎學金的原文名稱")
    name_zh: str | None = Field(description="中文名稱；原文不是中文就翻譯")
    provider: str | None = Field(description="提供單位")
    category_names: list[str] = Field(description="所有名額類別的名稱，照原文寫；只有一種就留空清單")


class CategoryFact(BaseModel):
    """長文件第二輪：一條適用於某些類別的規則。"""

    applies_to: list[str] = Field(
        description="這條規則適用的類別名稱，必須照抄類別清單裡的名稱；適用所有類別就填 [\"all\"]"
    )
    quota: int | None = Field(description="名額，只填數字；這條規則沒提到就留空")
    degrees: list[Degree] = Field(description="可以讀的學位；沒提到就留空清單")
    countries: list[str] = Field(description="可以去的國家，用英文國名；沒提到就留空清單")
    amount: str | None = Field(description="補助金額，照原文寫")
    eligibility: str | None = Field(description="資格條件")
    evidence: str | None = Field(description="這條規則的原文句子，逐字引用")


class SectionFacts(ProgramFacts):
    """長文件第二輪：從一節抽出的事實；這一節沒提到的欄位留空。"""

    category_facts: list[CategoryFact] = Field(description="這一節提到的類別規則")
    requirements: list[RequirementDraft] = Field(description="這一節提到的申請文件")
