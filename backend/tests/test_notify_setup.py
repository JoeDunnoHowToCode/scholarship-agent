"""Telegram 設定指令的單元測試：改寫 .env 時只動一個鍵，其他行（例如 token）原封不動。"""

from pathlib import Path

from app.core.notify import setup


def test_write_env_replaces_one_key_and_keeps_the_rest(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("GOOGLE_API_KEY=g\nTELEGRAM_BOT_TOKEN=t\nTELEGRAM_CHAT_ID=old\n# 註解\n")
    setup.write_env(env, "TELEGRAM_CHAT_ID", "12345")
    assert env.read_text() == "GOOGLE_API_KEY=g\nTELEGRAM_BOT_TOKEN=t\n# 註解\nTELEGRAM_CHAT_ID=12345\n"
    # 原本沒有這個鍵：加在最後；原本檔案最後沒有換行也不會黏在一起
    other = tmp_path / "other.env"
    other.write_text("TELEGRAM_BOT_TOKEN=t")
    setup.write_env(other, "TELEGRAM_CHAT_ID", "678")
    assert other.read_text() == "TELEGRAM_BOT_TOKEN=t\nTELEGRAM_CHAT_ID=678\n"
