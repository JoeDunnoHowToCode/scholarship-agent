"""國家代碼的單元測試（ADR-054）。"""

from app.features.scholarships import countries


def test_valid_code_is_an_uppercase_iso_code() -> None:
    # AI 填的國碼可能是小寫或多了空白；Kosovo 沒有 ISO 國碼，我們用 XK
    assert countries.valid_code("tw") == "TW"
    assert countries.valid_code(" fr ") == "FR"
    assert countries.valid_code("XK") == "XK"
    assert countries.valid_code("ZZ") is None  # 沒有這個國碼
    assert countries.valid_code("Taiwan") is None  # 國名不是國碼


def test_clean_codes_splits_good_and_bad_codes() -> None:
    # AI 會把同一國填兩次（TW、tw），也會把國名填進國碼欄（Korea）；無效的保留原本寫法，之後記進驗證結果的 issues
    assert countries.clean_codes(["TW", "tw", "ZZ", "FR", "Korea"]) == (["TW", "FR"], ["ZZ", "Korea"])
    # 無效的也去掉前後空白，重複的只列一次
    assert countries.clean_codes([" Korea", "Korea "]) == ([], ["Korea"])
