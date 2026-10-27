"""混合搜尋的名次合併（第 9 天，ADR-069）：關鍵字與語意各排一次名次，再合成一份。"""

# RRF 的常數 k：Cormack、Clarke、Büttcher 2009 年的論文（SIGIR）用 60；k 越大，名次之間的差距越小
K = 60


def rrf(rankings: list[list[int]], k: int = K) -> list[int]:
    """Reciprocal Rank Fusion：每份名單裡排第 r 名（從 1 算起）給 1/(k+r) 分，加總後由高到低排。

    兩份名單都有的會排前面；分數一樣時照第一次出現的順序（dict 保留加入順序，sorted 是穩定排序）。
    """
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, 1):
            scores[item] = scores.get(item, 0.0) + 1 / (k + rank)
    return sorted(scores, key=lambda item: -scores[item])
