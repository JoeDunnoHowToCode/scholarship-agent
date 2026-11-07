"""設定檔：.env 裡有的金鑰都要讀得進來，不能讓整個程式啟動失敗。"""

from pathlib import Path

from pydantic import ValidationError

from app.shared.settings import Settings


def test_tavily_key_in_env_file_is_read(tmp_path: Path) -> None:
    # 11-07 實際發生：使用者把 Tavily 金鑰寫進 .env，設定檔不認得這個欄位，所有程式一啟動就失敗
    env = tmp_path / ".env"
    env.write_text("TAVILY_API_KEY=test-key\n")
    try:
        loaded: Settings | None = Settings(_env_file=env)  # type: ignore[call-arg]
    except ValidationError:
        loaded = None
    assert loaded is not None, "有 TAVILY_API_KEY 的 .env 應該讀得進來"
    assert loaded.tavily_api_key is not None
    assert loaded.tavily_api_key.get_secret_value() == "test-key"
