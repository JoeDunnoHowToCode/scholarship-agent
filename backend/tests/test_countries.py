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


def test_country_names_for_display_and_source_text() -> None:
    # 網頁顯示常用名稱，不用 ISO 的「Taiwan, Province of China」；原文可能只寫 Korea（學程 221）、舊名或中文名，都要對得上國碼
    assert countries.display_name("TW") == "Taiwan"
    assert countries.display_name("XK") == "Kosovo"  # pycountry 沒有 XK
    assert countries.display_name("VN") == "Vietnam"  # pycountry 的名稱是 Viet Nam，常用名稱是 Vietnam
    assert countries.display_name("CZ") == "Czechia"  # 沒有常用名稱就用 pycountry 的名稱
    assert countries.display_name("ZZ") == "ZZ"  # 不認得的代碼直接顯示代碼
    assert "Korea" in countries.names_for("KR")
    assert "Democratic People's Republic of Korea" in countries.names_for("KP")
    assert "Czech Republic" in countries.names_for("CZ")
    # 先放顯示名稱，再放 pycountry 的寫法，最後是別名；重複的只留一次
    assert countries.names_for("TW") == [
        "Taiwan", "Taiwan, Province of China", "Republic of China", "Chinese Taipei", "台灣", "臺灣", "中華民國",
    ]
    assert countries.names_for("ZZ") == ["ZZ"]


def test_valid_code_maps_eu_style_codes_to_iso() -> None:
    # 歐盟文件習慣用 EL 代表希臘、UK 代表英國；ISO 的國碼是 GR、GB（第 6 天重抽時 AI 填了 EL）
    assert countries.valid_code("EL") == "GR"
    assert countries.valid_code(" uk ") == "GB"
