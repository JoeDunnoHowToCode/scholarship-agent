"""用向量相似度找出可能重複的獎學金。"""

import math
from itertools import combinations


def similar_pairs(vectors: dict[int, list[float]], threshold: float) -> list[tuple[int, int, float]]:
    """每兩個向量算餘弦相似度（方向越接近越像，1 是完全相同），回傳達到門檻的（a, b, 相似度）。

    長度是 0 的向量沒有方向，無法比較，直接略過。結果由最像的排到最不像，一樣像時照編號排。
    """
    norms = {key: math.sqrt(sum(x * x for x in vector)) for key, vector in vectors.items()}
    keys = sorted(key for key in vectors if norms[key] > 0)
    pairs = []
    # combinations 會產生每一對 (a, b) 各一次，而且 a 排在 b 前面
    for a, b in combinations(keys, 2):
        dot = sum(x * y for x, y in zip(vectors[a], vectors[b], strict=True))
        score = dot / (norms[a] * norms[b])
        if score >= threshold:
            pairs.append((a, b, score))
    return sorted(pairs, key=lambda pair: (-pair[2], pair[0], pair[1]))
