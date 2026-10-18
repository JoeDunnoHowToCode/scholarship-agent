"""篩選條件轉 SQL 的單元測試（ADR-051）。"""

from datetime import UTC, date, datetime

from sqlalchemy.dialects import postgresql

from app.features.search import filters

NOW = datetime(2026, 10, 18, tzinfo=UTC)


def sql_and_params(chosen: "filters.Filters") -> tuple[str, dict[str, object]]:
    compiled = filters.build_filter_query(chosen, NOW).compile(dialect=postgresql.dialect())
    return str(compiled), dict(compiled.params)


def test_filter_query_matches_nationality_degree_dates_and_open_cycles() -> None:
    # 「台灣可以申請、讀碩士、2027 年 1 月到 2 月截止、現在還能申請的」
    # 國籍要同時看獎學金和申請期：列出的國家要包含台灣、排除的國家不能包含台灣
    chosen = filters.Filters(
        nationality="Taiwan", degree="master", country=None,
        deadline_after=date(2027, 1, 1), deadline_before=date(2027, 2, 28), open_only=True,
    )
    sql, params = sql_and_params(chosen)
    assert "scholarships.duplicate_of IS NULL" in sql
    assert "cycles.estimated IS false" in sql
    assert "Taiwan" in params.values()
    assert "master" in params.values()
    assert "cycles.status IN" in sql
    assert datetime(2027, 1, 1, tzinfo=UTC) in params.values()
    assert datetime(2027, 3, 1, tzinfo=UTC) in params.values()  # 2/28 當天也算，所以上限是隔天 0 點
    assert "cycles.nationality_scope" in sql and "scholarships.nationality_scope" in sql


def test_empty_filters_only_drop_duplicates_and_estimates() -> None:
    # 什麼條件都沒給：不篩國籍、學位、日期，只排除重複的獎學金和預估的申請期
    chosen = filters.Filters(
        nationality=None, degree=None, country=None,
        deadline_after=None, deadline_before=None, open_only=False,
    )
    sql, params = sql_and_params(chosen)
    assert "nationality_scope" not in sql
    assert "cycles.status" not in sql
    assert "scholarships.duplicate_of IS NULL" in sql
