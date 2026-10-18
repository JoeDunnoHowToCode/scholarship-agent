"""向量相似度找重複的單元測試。"""

import math

import pytest

from app.features.search import similar


def test_similar_pairs_threshold_once_sorted_and_zero_skipped() -> None:
    # 用二維向量當作獎學金簡介的向量：1 和 2 方向相同（長度不同也算完全相似），
    # 3 和 1、2、5 都差 45 度；4 是全 0 的向量（沒內容），不能拿來比
    vectors = {
        3: [1.0, 1.0],
        1: [1.0, 0.0],
        5: [0.0, 2.0],
        2: [2.0, 0.0],
        4: [0.0, 0.0],
    }
    pairs = similar.similar_pairs(vectors, 0.7)
    # 每一對只出現一次、小編號在前；相似度由高到低，一樣高時照編號排
    assert [(a, b) for a, b, _ in pairs] == [(1, 2), (1, 3), (2, 3), (3, 5)]
    assert [score for _, _, score in pairs] == pytest.approx([1.0] + [1 / math.sqrt(2)] * 3)
    # 剛好等於門檻也算
    assert [(a, b) for a, b, _ in similar.similar_pairs(vectors, 1.0)] == [(1, 2)]
