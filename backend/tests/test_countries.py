"""國家代碼的單元測試（ADR-054）。"""

from app.features.scholarships import countries


def test_valid_code_is_an_uppercase_iso_code() -> None:
    # AI 填的國碼可能是小寫或多了空白；Kosovo 沒有 ISO 國碼，我們用 XK
    assert countries.valid_code("tw") == "TW"
    assert countries.valid_code(" fr ") == "FR"
    assert countries.valid_code("XK") == "XK"
    assert countries.valid_code("ZZ") is None  # 沒有這個國碼
    assert countries.valid_code("Taiwan") is None  # 國名不是國碼
