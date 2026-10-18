"""變更紀錄比對的單元測試（ADR-020）。"""

from app.features.scholarships import changes


def test_ignores_formatting_only_differences() -> None:
    # 每次重新抽取，模型會換空白、大小寫、清單順序，或換一句引用；內容沒變就不該記成變更
    old = {
        "amount": "EUR 1,400 per month",
        "coverage": "Tuition fees and living costs",
        "nationalities": ["Sweden", "Denmark"],
        "other_eligibility": None,
        "windows": [
            {
                "closes_year": 2027,
                "closes_month": 1,
                "closes_day": 31,
                "label": "Partner countries",
                "funding": "scholarship",
                "evidence": "Deadline: 31 January 2027",
            }
        ],
        "categories": [
            {
                "name": "北歐國家",
                "quota": 10,
                "degrees": ["master", "phd"],
                "degree_conditions": None,
                "quota_evidence": "(1)北歐國家(丹麥、瑞典、挪威、芬蘭、冰島)：10 名。",
                "degrees_evidence": "得攻讀碩士或博士學位",
            }
        ],
        "requirements": [
            {"doc_type": "cv", "details": "max 2 pages", "category": None, "evidence": "CV (max 2 pages)"},
            {"doc_type": "transcript", "details": None, "category": None, "evidence": "Official transcripts"},
        ],
    }
    new = {
        "amount": "  eur 1,400   PER month ",  # 多了空白、大小寫不同
        "coverage": "Ｔｕｉｔｉｏｎ fees and living costs",  # 全形字
        "nationalities": ["Denmark", "Sweden"],  # 順序不同
        "other_eligibility": "",  # 空字串等於沒有
        "windows": [
            {
                "closes_year": 2027,
                "closes_month": 1,
                "closes_day": 31,
                "label": "partner  countries",
                "funding": "scholarship",
                "evidence": "The application deadline is 31 January 2027.",  # 換了一句引用
            }
        ],
        "categories": [
            {
                "name": "北歐國家",
                "quota": 10,
                "degrees": ["phd", "master"],
                "degree_conditions": None,
                "quota_evidence": "北歐國家：10 名",
                "degrees_evidence": "得攻讀碩士或博士學位。",
            }
        ],
        "requirements": [
            {"doc_type": "transcript", "details": None, "category": None, "evidence": "Transcripts of records"},
            {"doc_type": "cv", "details": "Max 2 pages", "category": None, "evidence": "Curriculum vitae, max 2 pages"},
        ],
    }
    assert changes.diff_important(old, new) == []
