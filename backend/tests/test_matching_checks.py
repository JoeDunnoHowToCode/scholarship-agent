"""評分硬性條件與加權總分的單元測試（ADR-043、046、047、055）。"""

from dataclasses import replace

from app.features.matching import checks


def test_nationality_check_follows_the_scope_and_ignores_case() -> None:
    # Erasmus Mundus 開放全世界申請：任何國籍都符合
    assert checks.nationality_check("TW", "all", []) == "pass"
    # 教育部留學獎學金只限台灣籍：台灣人符合、韓國人不符合；國碼大小寫不同也一樣
    assert checks.nationality_check("tw", "listed", ["TW"]) == "pass"
    assert checks.nationality_check("KR", "listed", ["tw"]) == "fail"
    # 學程 20 夥伴國那期排除歐盟國家：台灣人符合、法國人不符合
    assert checks.nationality_check("TW", "excluded", ["FR", "DE"]) == "pass"
    assert checks.nationality_check("fr", "excluded", ["FR", "DE"]) == "fail"
    # 原文沒寫國籍資格：待確認
    assert checks.nationality_check("TW", "unclear", []) == "unclear"


def test_time_check_uses_only_cycles_that_apply_to_the_user() -> None:
    # 學程 20：夥伴國那期排除歐盟等 33 國（這裡只列 3 國），歐盟那期只限這些國家；都即將開放、截止日核對過
    partner = checks.CycleInfo(
        status="upcoming", nationality_scope="excluded", nationalities=("FR", "DE", "IT"),
        funding="scholarship", verified=True,
    )
    # replace：複製一份，只改寫到的欄位
    eu = replace(partner, nationality_scope="listed", funding="any")
    self_funded = replace(partner, nationality_scope="all", nationalities=(), funding="self_funded")
    closed = replace(partner, status="closed")
    # 台灣人適用夥伴國那期、不適用歐盟那期；自費生的截止日（例如學程 35 的 4 月底）申請獎學金的人不看
    assert checks.applicable([closed, eu, self_funded, partner], "TW") == [closed, partner]  # 順序照原本的
    assert checks.applicable([partner, eu], "FR") == [eu]
    # 完全沒有截止日：不知道來不來得及
    assert checks.time_check([], "TW") == "unclear"
    # 有截止日，但沒有一個是給台灣人申請獎學金的
    assert checks.time_check([eu, self_funded], "TW") == "fail"
    # 還能申請（即將開放或開放中）而且截止日核對過：符合；分兩輪收件時，第一輪截止了還有第二輪
    assert checks.time_check([partner, eu], "TW") == "pass"
    assert checks.time_check([closed, replace(partner, status="open")], "TW") == "pass"
    # 還能申請但截止日沒通過核對，或只剩程式猜的明年日期：待確認
    assert checks.time_check([replace(partner, verified=False)], "TW") == "unclear"
    assert checks.time_check([closed, replace(partner, status="estimated", verified=False)], "TW") == "unclear"
    # 適用的申請期都截止了：不符合
    assert checks.time_check([closed, eu], "TW") == "fail"
