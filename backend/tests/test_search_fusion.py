"""混合搜尋的名次合併（第 9 天，ADR-069）：Reciprocal Rank Fusion（RRF）。"""

from app.features.search import fusion


def test_rrf_merges_rankings_and_rewards_items_found_by_both() -> None:
    # 關鍵字找到獎學金 7、3；語意找到 3、5、9（數字是獎學金 id，照名次排）
    keyword = [7, 3]
    semantic = [3, 5, 9]
    # 每份名單排第 r 名（從 1 算起）給 1/(60+r) 分，加總後由高到低：
    # 3：1/62＋1/61（兩份都有，最高）；7：1/61；5：1/62；9：1/63
    assert fusion.rrf([keyword, semantic]) == [3, 7, 5, 9]
    # 只有一份名單：照原本的順序
    assert fusion.rrf([semantic]) == [3, 5, 9]
    # 分數一樣時，照第一次出現的順序（每次結果都一樣）
    assert fusion.rrf([[1, 2], [2, 1]]) == [1, 2]
    # 兩份都是空的：空清單
    assert fusion.rrf([[], []]) == []
