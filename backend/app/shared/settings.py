"""設定：從 backend/.env 與環境變數讀取（pydantic-settings）。"""

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env 的絕對路徑：不管從哪個資料夾執行，都讀同一個檔
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE)

    database_url: str = "postgresql+psycopg://scholar:scholar@localhost:5432/scholar"
    # 可以留空：用到 Gemini 時才檢查，不需要金鑰的步驟照常能跑
    google_api_key: SecretStr | None = None
    # 模型名稱放在設定裡（ADR-015）
    llm_model: str = "gemini-3.5-flash-lite"


settings = Settings()
