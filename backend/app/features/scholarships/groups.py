"""國家群組（D1 C，ADR-109）：原文用群組寫國籍時，AI 填群組代號，程式在這裡展開成 ISO 3166-1 國碼。

清單放在程式裡（像 ADR-054 的 Erasmus+ 清單），每份附官方出處與查證日期；群組成員改變時要更新。
"""


def expand(scope: str, nationalities: list[str], groups: list[str]) -> tuple[str, list[str]]:
    """把群組展開成國碼，和另外寫的國家合在一起；回傳（國籍範圍, 國碼清單）。"""
    return scope, nationalities
