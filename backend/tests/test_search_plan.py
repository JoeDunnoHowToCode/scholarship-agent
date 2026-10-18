"""沿用舊向量計畫的單元測試。"""

from app.features.search import plan


def test_reuse_same_hash_and_model_recompute_otherwise() -> None:
    # 簡章重新抓取後：第 0 段沒變（同模型算過）沿用；第 1 段是新內容；
    # 第 2 段內容沒變，但舊向量是用舊模型算的，必須重算
    kept = plan.Reusable(embedding=[0.1, 0.2], summary="獎助名額", topics=["名額"])
    stale = plan.Reusable(embedding=[0.3, 0.4], summary=None, topics=[])
    old = {
        ("hash-a", "text-embedding-3-small"): kept,
        ("hash-c", "old-model"): stale,
    }
    reused, to_compute = plan.reuse_plan(old, ["hash-a", "hash-b", "hash-c"], "text-embedding-3-small")
    assert reused == {0: kept}
    assert to_compute == [1, 2]
