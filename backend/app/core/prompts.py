"""提示詞檔（ADR-088）：一個版本一個檔，放在 backend/prompts/<名稱>/<號碼>.md。

版本號（例如 extract-12）同時是檔名和快取鍵的一部分（ADR-013）：
改提示詞就新增一個號碼更大的檔案，舊檔留著，方便第 11 天並排比較。
"""

from pathlib import Path
from string import Formatter

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"

# 這個程序載入過的提示詞（版本號 → 原文），identify 用它反查
_loaded: dict[str, str] = {}


def load(version: str) -> str:
    """依版本號讀提示詞，例如 load("extract-12") 讀 prompts/extract/12.md。"""
    name, number = version.rsplit("-", 1)  # 從最後一個「-」切開：extract-12 → extract、12
    # 檔案不存在時 read_text 會丟 FileNotFoundError：版本號打錯就馬上發現，不會送出空白提示詞
    text = (PROMPTS_DIR / name / f"{number}.md").read_text(encoding="utf-8")
    _loaded[version] = text
    return text


def identify(text: str) -> str | None:
    """送出去的文字是哪個提示詞的哪一版（ADR-089 記錄用）；認不出來回傳 None。"""
    best: tuple[int, str] | None = None
    for version, template in _loaded.items():
        # 提示詞裡固定的文字片段（變數 {name} 之間的部分）；Formatter 會把 {{ }} 還原成 { }
        pieces = [literal for literal, *_ in Formatter().parse(template) if literal]
        if pieces and _contains_in_order(text, pieces):
            size = sum(map(len, pieces))
            # 好幾個都符合時取固定文字最多的（最具體的那個）
            if best is None or size > best[0]:
                best = (size, version)
    return best[1] if best else None


def _contains_in_order(text: str, pieces: list[str]) -> bool:
    """第一段要在最開頭，其他段依序出現在後面（變數填進去的內容夾在中間）。"""
    if not text.startswith(pieces[0]):
        return False
    position = len(pieces[0])
    for piece in pieces[1:]:
        found = text.find(piece, position)
        if found < 0:
            return False
        position = found + len(piece)
    return True
