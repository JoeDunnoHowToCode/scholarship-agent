"""填個人資料的指令（第 6 天）：資料只存在本機的資料庫。

用法：uv run python -m app.features.profiles.set --nationality TW --degree master \
        [--major 目前科系] [--field 想讀的領域 …] [--country FR …]
"""

import argparse
import sys

from pydantic import ValidationError

from app.features.profiles.service import (
    CURRENT_USER_ID,
    ProfileIn,
    save_profile,
    to_out,
)
from app.shared.db import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description="填寫或更新個人資料（ADR-055）")
    parser.add_argument("--nationality", required=True, help="國籍，ISO 國碼，例如 TW")
    parser.add_argument("--degree", required=True, choices=["bachelor", "master", "phd"])
    parser.add_argument("--major", help="目前科系（選填）")
    parser.add_argument("--field", action="append", default=[], help="想讀的領域，可以給好幾次（選填）")
    parser.add_argument("--country", action="append", default=[], help="想去的國家國碼，可以給好幾次（選填）")
    args = parser.parse_args()
    try:
        data = ProfileIn(
            nationality=args.nationality,
            target_degree=args.degree,
            current_major=args.major,
            target_fields=args.field,
            target_countries=args.country,
        )
    except ValidationError as error:
        sys.exit(f"資料格式不對：{error.errors()[0]['msg']}")
    with SessionLocal() as session, session.begin():
        row = save_profile(session, CURRENT_USER_ID, data)
        print(to_out(row).model_dump_json(indent=2))


if __name__ == "__main__":
    main()
