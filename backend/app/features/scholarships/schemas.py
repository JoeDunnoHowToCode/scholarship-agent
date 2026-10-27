"""抽取用的 Pydantic schema（ADR-011、031、034、040）。

欄位的 description 會連同 schema 一起送給模型，等於是填表說明。
可能缺的欄位允許 null 或 unclear；關鍵欄位附逐字引用的 evidence，之後由驗證者核對原文。
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, create_model

Degree = Literal["bachelor", "master", "phd"]
# 國籍資格的範圍（ADR-043）：開放所有國籍、只限列出的國家、排除列出的國家、沒寫
NationalityScope = Literal["all", "listed", "excluded", "unclear"]
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
    degrees: list[Degree] = Field(
        description="這個類別可以讀的所有學位，包括要符合附加條件才能讀的（條件寫在 degree_conditions）"
    )
    countries: list[str] = Field(description="這個類別可以去的國家，用 ISO 3166-1 兩碼國碼（例如 FR、DE）")
    amount: str | None = Field(description="這個類別的補助金額，照原文寫")
    eligibility: str | None = Field(description="這個類別特有的資格條件")
    # ADR-046：名額和學位各有自己的引用，學位的附加條件另存一欄
    quota_evidence: str | None = Field(description="寫著這個類別名額的原文句子，逐字引用")
    degrees_evidence: str | None = Field(description="寫著這個類別可以讀哪些學位的原文句子，逐字引用")
    degree_conditions: str | None = Field(
        description="哪個學位要符合什麼條件才能讀，例如「碩士限藝術學群、建築規劃與設計學群」；所有學位都沒有條件就留空"
    )


# 金額的期間與用途（ADR-070）
AmountPeriod = Literal["month", "year", "total", "once", "unclear"]
AmountKind = Literal["living_allowance", "tuition_coverage", "travel", "other"]


class AmountDraft(BaseModel):
    """獎學金給你的一筆錢（ADR-070）；學費、申請費這類要你付的錢不列。"""

    value: float = Field(description="金額數字，照原文換成阿拉伯數字，例如「1 萬 6 千」填 16000、「1,400」填 1400")
    currency: str = Field(description="ISO 4217 三碼幣別，例如 EUR、USD、TWD、GBP")
    period: AmountPeriod = Field(
        description="每月填 month、每年填 year、整個學程的總額填 total、一次給的錢（例如安家費）填 once；原文沒說填 unclear"
    )
    kind: AmountKind = Field(
        description="用途：生活津貼 living_allowance、學費補助或減免 tuition_coverage、旅費 travel、其他 other"
    )
    applies_to: str | None = Field(description="適用對象，例如「一般生」「非歐盟學生」；所有人都一樣就留空")
    evidence: str | None = Field(description="寫著這個金額的原文句子，逐字引用")


class RequirementDraft(BaseModel):
    """申請要交的一份文件。"""

    doc_type: DocType = Field(description="文件類型代號；對不上就填 other")
    details: str | None = Field(description="具體要求，例如字數、格式、語言、要不要認證")
    required: bool | None = Field(description="必要填 true，選填填 false，原文沒說就留空")
    count: int | None = Field(description="份數，例如推薦信 2 封；原文沒說就留空")
    category: str | None = Field(description="只有某個類別要交時填類別名稱；所有人都要交就留空")
    evidence: str | None = Field(description="要求這份文件的原文句子，逐字引用")


# 截止日適用哪些申請人（ADR-047）：國籍範圍沿用 ADR-043 的寫法；申請類型分獎學金、自費、不分
WindowScope = Literal["all", "listed", "excluded"]
Funding = Literal["scholarship", "self_funded", "any"]


class WindowDraft(BaseModel):
    """一個申請窗口：某一屆、某一群申請人的開放日與截止日（ADR-047）。"""

    label: str | None = Field(
        description="原文怎麼稱呼這個截止日或它的適用對象，例如 Partner countries、第一輪；沒有就留空"
    )
    intake: str | None = Field(description="入學年度，例如 2027/28")
    opens_year: int | None = Field(description="開放申請日的西元年；沒寫就留空")
    opens_month: int | None = Field(description="開放申請日的月份；沒寫就留空")
    opens_day: int | None = Field(description="開放申請日的日；沒寫就留空")
    # ADR-045：原文沒寫年份時年份必須留空，不能自己補
    closes_year: int | None = Field(description="截止日的西元年；原文沒寫年份就留空，不要推測")
    closes_month: int | None = Field(description="截止日的月份 1–12；沒寫就留空")
    closes_day: int | None = Field(description="截止日的日 1–31；沒寫就留空")
    closes_time: str | None = Field(description="截止時間，24 小時制 HH:MM；沒寫就留空")
    timezone: str | None = Field(
        description="時區，用 IANA 名稱，例如 Europe/Paris、Asia/Taipei；原文寫「Paris time」就填 Europe/Paris；沒寫就留空"
    )
    nationality_scope: WindowScope = Field(
        description="這個截止日適用哪些國籍：不分國籍填 all；只限某些國家填 listed；除了某些國家都適用填 excluded"
    )
    nationalities: list[str] = Field(
        description="listed 或 excluded 時的國家，用 ISO 3166-1 兩碼國碼（例如台灣 TW、南韓 KR）；all 時留空清單"
    )
    funding: Funding = Field(
        description="適用申請獎學金的人填 scholarship；適用自費生填 self_funded；不分填 any"
    )
    evidence: str | None = Field(description="寫著這個截止日的原文句子，逐字引用")


class ProgramFacts(BaseModel):
    """整個獎學金共用的欄位。"""

    provider: str | None = Field(description="提供單位；原文沒寫就留空")
    countries: list[str] = Field(description="可以去留學的國家，用 ISO 3166-1 兩碼國碼（例如 FR、DE）")
    degrees: list[Degree] = Field(description="適用的學位")
    degrees_evidence: str | None = Field(description="支持學位的原文句子，逐字引用")
    fields: list[str] = Field(description="適用的領域，用英文；不限領域就留空清單")
    coverage: str | None = Field(description="補助內容，例如學費、生活費、機票")
    amounts: list[AmountDraft] = Field(
        description=(
            "獎學金給你的每一筆錢，每個金額一筆（生活津貼、學費補助或減免、旅費等）；"
            "學費、申請費這類要你付的錢不要列；原文沒寫金額就留空清單"
        )
    )
    nationality_scope: NationalityScope = Field(
        description=(
            "國籍資格：開放所有國籍填 all；只限某些國家填 listed；"
            "除了某些國家都可以填 excluded；原文沒寫填 unclear"
        )
    )
    nationalities: list[str] = Field(
        description=(
            "listed 或 excluded 時，列出的國家的 ISO 3166-1 兩碼國碼（例如台灣 TW、南韓 KR、北韓 KP）；"
            "其他情況留空清單"
        )
    )
    nationality_evidence: str | None = Field(description="描述國籍資格的原文句子，逐字引用")
    nationality_conditions: str | None = Field(
        description="特定國籍申請人的附加條件，例如台灣申請人需另附的文件"
    )
    language_requirements: str | None = Field(description="語言要求，例如 IELTS 6.5")
    other_eligibility: str | None = Field(description="其他資格條件，例如學歷、工作年資、年齡")
    requires_admission: bool | None = Field(
        description="申請獎學金前是否必須先拿到學校的入學許可；原文沒說就留空"
    )
    total_quota: int | None = Field(description="原文寫的總名額，只填數字；沒寫就留空")
    windows: list[WindowDraft] = Field(
        description="所有申請窗口；同一屆對不同申請人（國籍、獎學金或自費、第幾輪）有不同截止日時，每個各寫一筆"
    )


class ScholarshipDraft(ProgramFacts):
    """一個獎學金的完整抽取結果：一般網頁整份抽，或長文件合併後的結果。"""

    name: str = Field(description="獎學金或學程的原文名稱")
    name_zh: str | None = Field(description="中文名稱；原文不是中文就翻譯")
    categories: list[CategoryDraft] = Field(description="名額類別；只有一種也要填一個")
    requirements: list[RequirementDraft] = Field(description="申請要交的文件")


class OutlineCategory(BaseModel):
    """第一輪讀完全文後，每個類別的基本條件（跨章節的規則在這裡就能套上）。"""

    name: str = Field(description="類別名稱，和 category_names 一致")
    quota: int | None = Field(description="名額，只填數字")
    degrees: list[Degree] = Field(
        description="這個類別可以讀的所有學位，套用全文所有相關規則；包括要符合附加條件才能讀的"
    )
    countries: list[str] = Field(description="這個類別可以去的國家，用 ISO 3166-1 兩碼國碼（例如 FR、DE）；不限就留空清單")
    quota_evidence: str | None = Field(default=None, description="寫著名額的原文句子，逐字引用")
    degrees_evidence: str | None = Field(
        default=None, description="寫著可以讀哪些學位的原文句子，逐字引用"
    )
    degree_conditions: str | None = Field(
        default=None, description="哪個學位要符合什麼條件才能讀，例如「碩士限藝術學群」；沒有條件就留空"
    )


class Outline(BaseModel):
    """長文件第一輪：讀全文，只列名稱與類別清單（輸出短）。"""

    name: str = Field(description="獎學金的原文名稱")
    name_zh: str | None = Field(description="中文名稱；原文不是中文就翻譯")
    provider: str | None = Field(description="提供單位")
    category_names: list[str] = Field(description="所有名額類別的名稱，照原文寫；只有一種就留空清單")
    total_quota: int | None = Field(default=None, description="原文寫的總名額；沒寫就留空")
    category_details: list[OutlineCategory] = Field(
        default_factory=list, description="每個類別的名額、學位、國家，順序和 category_names 一致"
    )


class CategoryFact(BaseModel):
    """長文件第二輪：一條適用於某些類別的規則。"""

    applies_to: list[str] = Field(
        description="這條規則適用的類別名稱，必須照抄類別清單裡的名稱；適用所有類別就填 [\"all\"]"
    )
    quota: int | None = Field(
        description="這一個類別的名額，只填數字；applies_to 有好幾個類別時一律留空（那是總數，不是每類的名額）"
    )
    degrees: list[Degree] = Field(description="可以讀的學位；沒提到就留空清單")
    countries: list[str] = Field(description="可以去的國家，用 ISO 3166-1 兩碼國碼（例如 FR、DE）；沒提到就留空清單")
    amount: str | None = Field(description="補助金額，照原文寫")
    eligibility: str | None = Field(description="資格條件")
    degree_conditions: str | None = Field(
        default=None, description="哪個學位要符合什麼條件才能讀，例如「碩士限藝術學群」；沒有條件就留空"
    )
    evidence: str | None = Field(description="這條規則的原文句子，逐字引用")


class SectionFacts(ProgramFacts):
    """長文件第二輪：從一節抽出的事實；這一節沒提到的欄位留空。"""

    category_facts: list[CategoryFact] = Field(description="這一節提到的類別規則")
    requirements: list[RequirementDraft] = Field(description="這一節提到的申請文件")


def section_schema(category_names: list[str]) -> type[SectionFacts]:
    """第二輪的 schema 依第一輪的類別名稱動態產生（ADR-045 格式限制）。

    applies_to 與文件的 category 變成選單（JSON schema 的 enum），模型只能從清單挑，
    寫不出清單以外的名稱。
    """
    # 執行時才知道選項，型別檢查器看不懂，所以標成 Any
    names: Any = Literal[(*category_names, "all")]
    targets: Any = Literal[tuple(category_names)] if category_names else Literal["all"]
    fact: Any = create_model(
        "CategoryFactChoice",
        __base__=CategoryFact,
        applies_to=(list[names], Field(description="這條規則適用的類別；適用所有類別填 all")),
    )
    requirement: Any = create_model(
        "RequirementChoice",
        __base__=RequirementDraft,
        category=(
            targets | None,
            Field(description="只有某個類別要交時選類別名稱；所有人都要交就留空"),
        ),
    )
    return create_model(
        "SectionFactsChoice",
        __base__=SectionFacts,
        category_facts=(list[fact], Field(description="這一節提到的類別規則")),
        requirements=(list[requirement], Field(description="這一節提到的申請文件")),
    )
