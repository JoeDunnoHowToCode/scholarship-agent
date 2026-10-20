"""評分硬性條件與加權總分的單元測試（ADR-043、046、047、055）。"""

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
