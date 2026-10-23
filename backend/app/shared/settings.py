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
    # 每個程序每分鐘最多幾次 Gemini 請求（ADR-042）；平行跑 N 個程序時總量是 N 倍
    llm_requests_per_minute: int = 60
    # 嵌入模型（ADR-050）：維度固定在 scholarships.models.EMBEDDING_DIMENSIONS
    embedding_model: str = "gemini-embedding-2"
    # 同一個網站兩次請求至少間隔幾秒（ADR-028）；robots.txt 的 Crawl-delay 更長就照它
    fetch_min_interval_seconds: float = 5.0
    # 背景工作的佇列（ADR-004、006）：Docker 裡的 Redis，只綁本機
    redis_url: str = "redis://localhost:6379/0"


settings = Settings()
