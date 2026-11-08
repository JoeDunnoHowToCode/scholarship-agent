"""當天重試沒用的錯誤（11-08）：不重試，但當天照樣算失敗（ADR-080 的連續天數不受影響）。"""

import socket

import httpcore
import httpx
import pytest

from app.features.pipeline import jobs


def dns_error() -> BaseException:
    inner = socket.gaierror(socket.EAI_NONAME, "nodename nor servname provided, or not known")
    middle = httpcore.ConnectError("連線失敗")
    middle.__cause__ = inner
    outer = httpx.ConnectError("連線失敗")
    outer.__cause__ = middle
    return outer


def test_hopeless_errors_end_today_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jobs, "online", lambda: True)
    result = jobs.handle_error(None, 7, dns_error())  # type: ignore[arg-type]
    assert result["result"] == "unreachable"
    assert "gaierror" in result["detail"] and "nodename" in result["detail"]  # 記最裡面的真正原因


def test_when_offline_the_same_error_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    # 電腦斷網時 DNS 也會回「網域不存在」：不能當成官網的問題
    monkeypatch.setattr(jobs, "online", lambda: False)
    with pytest.raises(httpx.ConnectError):
        jobs.handle_error(None, 7, dns_error())  # type: ignore[arg-type]


def test_unreachable_results_count_as_failed_days() -> None:
    detail = "gaierror: [Errno 8] nodename nor servname provided"
    assert jobs.outcome_of(7, False, None, {"result": "unreachable", "detail": detail}) == (7, True, detail)
    # 重試完還失敗的：錯誤說明取最後一行
    assert jobs.outcome_of(8, True, "Traceback\n  ...\nhttpx.ConnectTimeout: timed out\n", None) == (
        8, True, "httpx.ConnectTimeout: timed out",
    )
    assert jobs.outcome_of(9, False, None, {"result": "unchanged", "detail": "內容沒變"}) == (9, False, "")
    # 每日報告的「抓不到」也把它算進去
    assert jobs.result_key(False, {"result": "unreachable"}) == "failed"
    assert jobs.result_key(True, None) == "failed"
    assert jobs.result_key(False, {"result": "noise"}) == "noise"
