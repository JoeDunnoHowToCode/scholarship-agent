"""提示詞檔（ADR-088）：一個版本一個檔，放在 backend/prompts/<名稱>/<號碼>.md。

版本號（例如 extract-12）同時是檔名和快取鍵的一部分（ADR-013）：
改提示詞就新增一個號碼更大的檔案，舊檔留著，方便第 11 天並排比較。
"""

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def load(version: str) -> str:
    """依版本號讀提示詞，例如 load("extract-12") 讀 prompts/extract/12.md。"""
    name, number = version.rsplit("-", 1)  # 從最後一個「-」切開：extract-12 → extract、12
    # 檔案不存在時 read_text 會丟 FileNotFoundError：版本號打錯就馬上發現，不會送出空白提示詞
    return (PROMPTS_DIR / name / f"{number}.md").read_text(encoding="utf-8")
