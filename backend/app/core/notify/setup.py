"""設定 Telegram 通知（第 8 天，ADR-063）：找到你的聊天 ID、寫進 backend/.env、送一則測試訊息。

用法：先在 Telegram 打開你的機器人，按 Start 或傳一句話，再執行
uv run python -m app.core.notify.setup

聊天 ID 只寫進 .env，不印出來；Telegram 只保留 24 小時內的訊息，太久以前傳的要再傳一句。
"""

import sys
from pathlib import Path

from app.core.notify.telegram_api import call
from app.shared.settings import ENV_FILE


def write_env(path: Path, key: str, value: str) -> None:
    """把 .env 裡的 key 改成 value：舊的那一行拿掉、新的加在最後，其他行（例如 token）原封不動。"""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    kept = [line for line in lines if not line.startswith(f"{key}=")]
    path.write_text("\n".join([*kept, f"{key}={value}"]) + "\n", encoding="utf-8")


def main() -> None:
    updates = call("getUpdates", {"allowed_updates": ["message"]})
    chats = [u["message"]["chat"] for u in updates if u.get("message", {}).get("chat", {}).get("type") == "private"]
    if not chats:
        sys.exit(
            "找不到傳給機器人的訊息：先在 Telegram 打開你的機器人，按 Start 或傳一句話，再執行一次"
            "（Telegram 只保留 24 小時內的訊息）"
        )
    chat = chats[-1]  # 最近一則私訊
    # 印出名稱讓你確認是自己（萬一有別人先傳訊息給這個機器人）；只出現在你的終端機
    who = " ".join(part for part in (chat.get("first_name"), f"@{chat['username']}" if chat.get("username") else None) if part)
    write_env(ENV_FILE, "TELEGRAM_CHAT_ID", str(chat["id"]))
    call("sendMessage", {"chat_id": chat["id"], "text": "留學獎學金通知設定完成：之後的通知會傳到這裡。"})
    print(f"完成：找到的聊天是「{who}」，聊天 ID 已寫進 backend/.env，也送了一則測試訊息，請到 Telegram 確認")
    print("如果那不是你：自己傳一句話給機器人，再執行一次這個指令（會改用最近一則私訊）")


if __name__ == "__main__":
    main()
