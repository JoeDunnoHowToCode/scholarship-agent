"""把長文件依標題結構切成段落（ADR-038）；表格自成一段（ADR-036 A）。"""

import re
from dataclasses import dataclass
from typing import Literal

# 一段文字最多幾個字（超過就切開）
MAX_CHARS = 3_000
# 一段文字至少幾個字（太短就併進上一段，避免一段只有一兩句、缺上下文）
MIN_CHARS = 200

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

# Markdown 標題：1 到 4 個 #，接空白，再接標題文字
MARKDOWN_HEADING = re.compile(r"^(#{1,4})\s+(.+)$")


# 段落種類：一般文字，或一整張表格
ChunkKind = Literal["text", "table"]


@dataclass(frozen=True)
class Chunk:
    heading_path: tuple[str, ...]  # 從最上層到這一段的標題
    text: str
    kind: ChunkKind


def _parse_heading(line: str) -> tuple[int, str] | None:
    """這一行是標題就回傳 (層級, 去掉 # 的標題文字)，不是就回傳 None。"""
    markdown = MARKDOWN_HEADING.match(line)
    text = markdown.group(2) if markdown else line
    if TOC_LINE.search(text):
        return None
    # 有公文編號就看編號；沒有編號的 Markdown 標題看 # 的數量
    for level, pattern in NUMBERING_LEVELS:
        if pattern.match(text):
            return level, text
    if markdown:
        return len(markdown.group(1)), text
    return None


def chunk_transcript(markdown: str) -> list[Chunk]:
    """逐行讀 Gemini 轉出的 Markdown，遇到標題就開新的一段。"""
    chunks: list[Chunk] = []
    stack: list[tuple[int, str]] = []  # 目前所在的標題：(層級, 標題文字)
    path: tuple[str, ...] = ()
    lines: list[str] = []
    kind: ChunkKind = "text"
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        heading = _parse_heading(line)
        # 以 | 開頭的行是 Markdown 表格的一列
        line_kind: ChunkKind = "table" if line.startswith("|") else "text"
        if heading is not None or line_kind != kind:
            # 遇到標題，或在文字和表格之間切換：先把上一段收起來
            chunks.append(Chunk(path, "\n".join(lines).strip(), kind))
            lines = []
            kind = line_kind
        if heading is not None:
            # 更新標題堆疊：同層或更深的標題都要退出
            level, line = heading
            stack = [entry for entry in stack if entry[0] < level]
            stack.append(heading)
            path = tuple(text[:HEADING_PATH_CHARS] for _, text in stack)
        lines.append(line)
    chunks.append(Chunk(path, "\n".join(lines).strip(), kind))
    chunks = [chunk for chunk in chunks if chunk.text]
    pieces = [piece for chunk in chunks for piece in _split_long(chunk)]
    return _merge_short(pieces)


def _merge_short(chunks: list[Chunk]) -> list[Chunk]:
    """太短的文字段落併進上一段：上一段也是文字、同一個最上層標題、併完不超過上限。"""
    merged: list[Chunk] = []
    for chunk in chunks:
        previous = merged[-1] if merged else None
        if (
            previous is not None
            and chunk.kind == "text"
            and previous.kind == "text"
            and len(chunk.text) < MIN_CHARS
            and chunk.heading_path[:1] == previous.heading_path[:1]
            and len(previous.text) + 1 + len(chunk.text) <= MAX_CHARS
        ):
            # 併進去的段落沿用上一段的標題路徑
            merged[-1] = Chunk(previous.heading_path, previous.text + "\n" + chunk.text, "text")
        else:
            merged.append(chunk)
    return merged


def _pack(parts: list[str], separator: str, limit: int) -> list[str]:
    """依序把小塊接起來；接上下一塊會超過 limit 就另起一塊（不會切開任何一塊）。"""
    packed: list[str] = []
    for part in parts:
        if packed and len(packed[-1]) + len(separator) + len(part) <= limit:
            packed[-1] += separator + part
        else:
            packed.append(part)
    return packed


def _split_long(chunk: Chunk) -> list[Chunk]:
    """太長的文字段落在換行處切開；單獨一行就太長時照字數硬切。表格不切。"""
    if chunk.kind == "table" or len(chunk.text) <= MAX_CHARS:
        return [chunk]
    parts = [
        line[start : start + MAX_CHARS]
        for line in chunk.text.splitlines()
        for start in range(0, len(line), MAX_CHARS)
    ]
    return [Chunk(chunk.heading_path, piece, "text") for piece in _pack(parts, "\n", MAX_CHARS)]
