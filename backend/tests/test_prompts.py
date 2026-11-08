"""提示詞放在檔案裡（ADR-088）：搬過去之後，送給 AI 的文字必須一字不差。"""

import hashlib

import pytest

from app.core import prompts
from app.features.documents import transcribe
from app.features.matching import score
from app.features.scholarships import extract, verify
from app.features.search import ask, index
from app.features.sources import pick

# 每個提示詞填入固定的範例值後，算出來的雜湊。這些雜湊是搬家前（11-08）用程式裡的字串常數算的：
# 只要檔案裡的文字和原本差一個字，雜湊就不同，測試就會失敗
SAMPLE = {
    "text": "<text>", "name": "<name>", "categories": "<categories>", "claims": "<claims>",
    "scholarship": "<scholarship>", "applicant": "<applicant>", "tables": "<tables>", "chunks": "<chunks>",
    "today": "<today>", "question": "<question>", "context": "<context>", "url": "<url>",
    "max_picks": "<max_picks>", "links": "<links>",
}
PINNED = {
    # 版本號: (要填的變數, 搬家前的雜湊)
    "extract-12": (["text"], "8e7e922092530e4b426171c140210c9404fcf5adaf246e6869e6cf7e852a8467"),
    "outline-8": (["text"], "e20da5a4d5c5b4693fb9fb272dfe9dea06f8d0e9dc84431206b9612653ac6d26"),
    "section-12": (["name", "categories", "text"], "ca11ce63d69eeca4f91e59624f89f4d68b5e853f0edb6347ddd0aa32aad682e1"),
    "amounts-1": (["text"], "d528395a24c14fe6d1c0fd4b11236ead72917dcdb0c8f452d969f27c33b15382"),
    "verify-5": (["claims"], "c796eaa0ae4bcfbc3f6d8cca8efd1ddba81c4e1e3246696d3b93377693280bcf"),
    "score-4": (["scholarship", "applicant"], "6263a6eec57d97a0b58501bc22b9bff19266f050676eaa41c60ea51582ee19da"),
    "table-1": (["tables"], "2e417baa52ecda87d4cfeef08821ff68739907c30e1eba206d922f65452dc283"),
    "topics-1": (["chunks"], "2aa825d256ad85387face8ad1c16e5d50a9611e1ea432dd3fc861db8bbc94049"),
    "route-2": (["today", "question"], "6ec9360170c81f842ea04d325c3928e02f9d9649118d7fb0130ee6d8941c8af6"),
    "answer-2": (["question", "context"], "a193b84bc9922fdc55a3d478d6c1d5c229f0eb2fa15374f611698a783fbc045f"),
    "links-1": (["name", "url", "max_picks", "links"], "217539386476274e52a4ee3fb32cb7a49f3db8c71d85f7bf9800fdda2c125a90"),
    "transcribe-1": ([], "016a4879a5be8be4a133ba78c3cb5d24343ee66791377070baa5f81503380154"),  # 直接送出，不填變數
}


@pytest.mark.parametrize("version", list(PINNED))
def test_prompt_file_renders_exactly_as_before(version: str) -> None:
    keys, pinned = PINNED[version]
    template = prompts.load(version)
    rendered = template.format(**{key: SAMPLE[key] for key in keys}) if keys else template
    assert hashlib.sha256(rendered.encode()).hexdigest() == pinned


def test_modules_use_the_file_matching_their_version() -> None:
    # 程式裡的版本號（快取鍵）和實際送出的提示詞必須是同一份：版本號換了，文字一定跟著換
    pairs = [
        (extract.PROMPT_VERSION, extract.EXTRACT_PROMPT),
        (extract.OUTLINE_VERSION, extract.OUTLINE_PROMPT),
        (extract.SECTION_VERSION, extract.SECTION_PROMPT),
        (extract.AMOUNTS_VERSION, extract.AMOUNTS_PROMPT),
        (verify.PROMPT_VERSION, verify.PROMPT),
        (score.PROMPT_VERSION, score.PROMPT),
        (index.TABLE_VERSION, index.TABLE_PROMPT),
        (index.TOPIC_VERSION, index.TOPIC_PROMPT),
        (ask.ROUTE_VERSION, ask.ROUTE_PROMPT),
        (ask.ANSWER_VERSION, ask.ANSWER_PROMPT),
        (pick.PROMPT_VERSION, pick.PROMPT),
        (transcribe.PROMPT_VERSION, transcribe.PROMPT),
    ]
    for version, text in pairs:
        assert text == prompts.load(version), version


def test_unknown_version_raises() -> None:
    with pytest.raises(FileNotFoundError):
        prompts.load("extract-999")
