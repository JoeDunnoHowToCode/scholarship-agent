"""把長文件依標題結構切成段落（ADR-038）；表格自成一段（ADR-036 A）。"""

import re
from dataclasses import dataclass
from typing import Literal

# 標題路徑裡每個標題最多留幾個字（太長的標題通常是整句話）
HEADING_PATH_CHARS = 40

# 公文的編號決定標題層級：壹、→ 第一層，一、→ 第二層，(一) → 第三層
NUMBERING_LEVELS = [
    (1, re.compile(r"^[壹貳參肆伍陸柒捌玖拾]+、")),
    (2, re.compile(r"^[一二三四五六七八九十]+、")),
    (3, re.compile(r"^[(（][一二三四五六七八九十]+[)）]")),
]

# 目錄行：結尾是 3 個以上的點點點，再接頁碼，例如「一、設置目的………… 2」
TOC_LINE = re.compile(r"[.…．]{3,}\s*\d+$")


@dataclass(frozen=True)
class Chunk:
    heading_path: tuple[str, ...]  # 從最上層到這一段的標題
    text: str
    kind: Literal["text", "table"]


def _heading_level(line: str) -> int | None:
    """這一行是標題就回傳層級，不是就回傳 None。"""
    if TOC_LINE.search(line):
        return None
    for level, pattern in NUMBERING_LEVELS:
        if pattern.match(line):
            return level
    return None


def chunk_transcript(markdown: str) -> list[Chunk]:
    """逐行讀 Gemini 轉出的 Markdown，遇到標題就開新的一段。"""
    chunks: list[Chunk] = []
    stack: list[tuple[int, str]] = []  # 目前所在的標題：(層級, 標題文字)
    path: tuple[str, ...] = ()
    lines: list[str] = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        level = _heading_level(line)
        if level is not None:
            # 先把上一段收起來，再更新標題堆疊：同層或更深的標題都要退出
            chunks.append(Chunk(path, "\n".join(lines).strip(), "text"))
            lines = []
            stack = [entry for entry in stack if entry[0] < level]
            stack.append((level, line))
            path = tuple(text[:HEADING_PATH_CHARS] for _, text in stack)
        lines.append(line)
    chunks.append(Chunk(path, "\n".join(lines).strip(), "text"))
    return [chunk for chunk in chunks if chunk.text]
