"""檢查回答裡標的來源編號：只能引用真的提供給模型的來源。"""


def valid_citations(cited: list[str], allowed: set[str]) -> tuple[list[str], list[str]]:
    """把引用的編號分成（有效, 無效）兩組；重複的只留第一次出現的。"""
    unique = list(dict.fromkeys(cited))  # dict 會記住放入順序，用來去重又保留順序
    kept = [cid for cid in unique if cid in allowed]
    invalid = [cid for cid in unique if cid not in allowed]
    return kept, invalid
