"""內容沒變的段落沿用舊向量，不必重新花錢計算。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Reusable:
    """之前算好、可以沿用的結果。"""

    embedding: list[float]
    summary: str | None
    topics: list[str]


def reuse_plan(
    old: dict[tuple[str, str], Reusable], hashes: list[str], model_id: str
) -> tuple[dict[int, Reusable], list[int]]:
    """依（內容雜湊, 向量模型）找舊結果：找到就沿用，找不到的段落編號要重算。

    內容一樣但舊向量是別的模型算的也要重算：不同模型的向量不能放在一起比較。
    """
    reused: dict[int, Reusable] = {}
    to_compute: list[int] = []
    for i, content_hash in enumerate(hashes):
        found = old.get((content_hash, model_id))
        if found is None:
            to_compute.append(i)
        else:
            reused[i] = found
    return reused, to_compute
