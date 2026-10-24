"""設定 Telegram 通知（第 8 天，ADR-063）：找到你的聊天 ID、寫進 backend/.env、送一則測試訊息。"""

from pathlib import Path


def write_env(path: Path, key: str, value: str) -> None:
    """把 .env 裡的 key 改成 value：舊的那一行拿掉、新的加在最後，其他行（例如 token）原封不動。"""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    kept = [line for line in lines if not line.startswith(f"{key}=")]
    path.write_text("\n".join([*kept, f"{key}={value}"]) + "\n", encoding="utf-8")
