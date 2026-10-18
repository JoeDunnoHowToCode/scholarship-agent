"""回答來源編號檢查的單元測試。"""

from app.features.search import citations


def test_valid_citations_split_kept_and_invalid() -> None:
    # 模型只拿到 C1、C3、F1 三個來源，卻引用了不存在的 C9；重複的 C3 只留一次
    kept, invalid = citations.valid_citations(["C3", "C9", "C3", "F1"], {"C1", "C3", "F1"})
    assert kept == ["C3", "F1"]
    assert invalid == ["C9"]
    # 編造的編號重複出現也只列一次
    assert citations.valid_citations(["X2", "X2"], {"C1"}) == ([], ["X2"])
