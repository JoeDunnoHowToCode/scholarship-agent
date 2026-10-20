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


def test_degree_check_marks_degrees_with_conditions_unclear() -> None:
    # 教育部北歐國家：原則上只能讀博士，碩士限藝術、建築學群（ADR-046）；程式不判斷使用者的學群，只標待確認
    nordic = "碩士限藝術學群、建築規劃與設計學群"
    assert checks.degree_check("master", ["master", "phd"], nordic) == "unclear"
    assert checks.degree_check("phd", ["master", "phd"], nordic) == "pass"  # 條件只講碩士，讀博士不受影響
    # 沒有附加條件：清單裡有就符合，沒有就不符合
    assert checks.degree_check("master", ["master", "phd"], None) == "pass"
    assert checks.degree_check("master", ["master", "phd"], "") == "pass"
    assert checks.degree_check("bachelor", ["master", "phd"], None) == "fail"
    # 原文沒寫學位：待確認
    assert checks.degree_check("master", [], None) == "unclear"


def test_weighted_total_rescales_over_the_scored_items() -> None:
    # AI 給四項 0–10 分（ADR-055 拿掉「條件達成度」後的權重）：全部滿分是 100，只有領域滿分是 40
    assert checks.weighted_total({"field": 10, "value": 10, "timing": 10, "competition": 10}) == 100.0
    assert checks.weighted_total({"field": 10, "value": 0, "timing": 0, "competition": 0}) == 40.0
    # AI 沒給領域分數：只用其他三項的權重換算，10 ×（0.27×10 + 0.20×0 + 0.13×10）÷ 0.60 ≈ 66.7
    assert checks.weighted_total({"field": None, "value": 10, "timing": 0, "competition": 10}) == 66.7
    # 拿掉的「條件達成度」就算還有分數也不算；一項分數都沒有就是 0
    assert checks.weighted_total({"field": 8, "conditions": 10}) == 80.0
    assert checks.weighted_total({"field": None}) == 0.0
    assert checks.weighted_total({}) == 0.0


def test_rule_order_guards_found_by_mutation_testing() -> None:
    # sub agent 故意把規則改錯 11 種方式，其中 4 種原本的測試抓不到；這些斷言把順序與大小寫固定下來
    # 國碼清單是小寫也要比得到
    assert checks.nationality_check("TW", "listed", ["tw"]) == "pass"
    # 有一個驗證通過、還能申請的申請期就算符合，不會被另一個沒驗證或預估的申請期拉成待確認
    partner = checks.CycleInfo(
        status="open", nationality_scope="excluded", nationalities=("FR", "DE", "IT"),
        funding="scholarship", verified=True,
    )
    assert checks.time_check([replace(partner, verified=False), partner], "TW") == "pass"
    assert checks.time_check([replace(partner, status="estimated", verified=False), partner], "TW") == "pass"
    # 想讀的學位不在清單裡就是不符合，就算條件文字有提到這個學位
    assert checks.degree_check("master", ["phd"], "碩士限藝術學群") == "fail"


def test_nationality_check_without_a_country_list_is_unclear() -> None:
    # 有國籍限制、但 AI 沒列出是哪些國家（學程 78「for non-European applicants」、學程 15「African Union 會員國」）：
    # 不知道台灣在不在裡面，不能判不符合，也不能判符合
    assert checks.nationality_check("TW", "listed", []) == "unclear"
    assert checks.nationality_check("TW", "excluded", []) == "unclear"


def test_time_check_counts_cycles_with_unknown_nationality_as_unclear() -> None:
    # 學程 78：「3 January 2027 (for non-European applicants)」被抽成只限列出的國家、卻沒有清單；
    # 台灣人可能適用，所以是待確認，不是不符合；那一期截止了就還是不符合
    unknown = checks.CycleInfo(
        status="open", nationality_scope="listed", nationalities=(), funding="scholarship", verified=True,
    )
    assert checks.time_check([unknown], "TW") == "unclear"
    assert checks.time_check([replace(unknown, status="closed")], "TW") == "fail"
