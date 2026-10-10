"""種子來源（ADR-026、ADR-029）：寫入或更新 3 個起始來源，重跑也不會重複。

用法：uv run python -m app.features.sources.seed
"""

from typing import Any

from sqlalchemy.dialects.postgresql import insert

from app.features.sources.models import FetchMethod, Source, SourceKind
from app.shared.db import SessionLocal

SEEDS: list[dict[str, Any]] = [
    {
        "name": "Erasmus Mundus Catalogue",
        "url": "https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en",
        "kind": SourceKind.GOVERNMENT,  # 歐盟執行機構的官方目錄
        "country": "European Union",
        "fetch_method": FetchMethod.HTML,
        "follow_pagination": True,  # 約 220 個學程分在 11 頁
        "page_zero_is_first": True,  # ?page=0 就是首頁本身（實測內容雜湊相同）
    },
    {
        "name": "Chevening Taiwan",
        "url": "https://www.chevening.org/scholarship/taiwan/",
        "kind": SourceKind.GOVERNMENT,  # 英國政府的獎學金
        "country": "United Kingdom",
        "fetch_method": FetchMethod.HTML,
        "follow_pagination": False,
    },
    {
        "name": "教育部 115 年留學獎學金簡章",
        "url": "https://ws.moe.edu.tw/001/Upload/7/relfile/9909/103401/7332fb46-00f7-4ed4-9af7-6fc63a301b13.pdf",
        "kind": SourceKind.GOVERNMENT,
        "country": "Taiwan",
        "fetch_method": FetchMethod.PDF,
        "follow_pagination": False,
    },
]


def main() -> None:
    with SessionLocal() as session, session.begin():
        for seed in SEEDS:
            # 網址已存在就更新其他欄位（upsert），所以重跑不會多出重複的來源
            changes = {key: value for key, value in seed.items() if key != "url"}
            statement = (
                insert(Source)
                .values(**seed)
                .on_conflict_do_update(index_elements=[Source.url], set_=changes)
            )
            session.execute(statement)
    print(f"已寫入或更新 {len(SEEDS)} 個種子來源")


if __name__ == "__main__":
    main()
