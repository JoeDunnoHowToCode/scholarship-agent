"""要變成向量的文字：段落標題和獎學金簡介。"""


def chunk_title(heading_path: list[str]) -> str:
    """段落所在的標題路徑，例如「簡章 > 四、獎助類別及名額」；空白的標題略過。"""
    return " > ".join(heading.strip() for heading in heading_path if heading.strip())
