"""登入後自動啟動 worker 與排程器（ADR-061）：產生 macOS launchd 的設定檔並載入。

用法：uv run python -m app.features.pipeline.launchd install     安裝，並馬上啟動
      uv run python -m app.features.pipeline.launchd uninstall   停止並移除
      uv run python -m app.features.pipeline.launchd status      看兩個程式有沒有在跑

安裝會在 ~/Library/LaunchAgents 加兩個檔案（登入項目）；移除會把它們刪掉。
"""

import argparse
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3]  # backend/
LOGS = BACKEND / "data" / "logs"
AGENTS = Path.home() / "Library" / "LaunchAgents"
# 標籤是 launchd 用來辨認程式的名字；後面是要執行的指令（前面會自動加上 uv run）
JOBS = {
    "local.scholarship-agent.worker": ["rq", "worker", "-w", "rq.worker.SpawnWorker", "--with-scheduler"],
    "local.scholarship-agent.cron": ["rq", "cron", "app.features.pipeline.schedule"],
}


def plist_for(label: str, command: list[str], uv: str) -> dict[str, object]:
    """一個程式的 launchd 設定：登入時啟動、當掉自動重開、輸出寫進 data/logs。"""
    log = str(LOGS / f"{label.rsplit('.', 1)[-1]}.log")
    return {
        "Label": label,
        "ProgramArguments": [uv, "run", *command],
        "WorkingDirectory": str(BACKEND),
        "RunAtLoad": True,  # 登入（載入）時就啟動
        "KeepAlive": True,  # 當掉自動重開，例如登入時 Docker 還沒啟動、連不到 Redis
        "StandardOutPath": log,
        "StandardErrorPath": log,
        # launchd 給的 PATH 很短，補上 uv 所在的資料夾
        "EnvironmentVariables": {"PATH": f"{Path(uv).parent}:/usr/bin:/bin:/usr/sbin:/sbin"},
    }


def domain() -> str:
    return f"gui/{os.getuid()}"  # 目前登入的這位使用者


def install() -> None:
    uv = shutil.which("uv")
    if uv is None:
        sys.exit("找不到 uv：先確認在終端機打 uv 可以執行")
    LOGS.mkdir(parents=True, exist_ok=True)
    AGENTS.mkdir(parents=True, exist_ok=True)
    for label, command in JOBS.items():
        path = AGENTS / f"{label}.plist"
        if path.exists():
            # 已經裝過：先停掉舊的，再用新的設定啟動
            subprocess.run(["launchctl", "bootout", f"{domain()}/{label}"], check=False)
        with path.open("wb") as file:
            plistlib.dump(plist_for(label, command, uv), file)
        subprocess.run(["launchctl", "bootstrap", domain(), str(path)], check=True)
        print(f"已安裝並啟動：{label}（{path}）")


def uninstall() -> None:
    for label in JOBS:
        subprocess.run(["launchctl", "bootout", f"{domain()}/{label}"], check=False)
        (AGENTS / f"{label}.plist").unlink(missing_ok=True)
        print(f"已停止並移除：{label}")


def status() -> None:
    # launchctl list 每行是「PID、上次結束代碼、標籤」，用 tab 分開；沒在跑的 PID 是 -
    listing = subprocess.run(["launchctl", "list"], capture_output=True, text=True, check=True).stdout
    rows = {parts[2]: parts for parts in (line.split("\t") for line in listing.splitlines()) if len(parts) == 3}
    for label in JOBS:
        if label not in rows:
            print(f"{label}：沒有安裝")
            continue
        pid, last_exit, _ = rows[label]
        state = f"執行中（PID {pid}）" if pid != "-" else "沒在跑"
        print(f"{label}：{state}，上次結束代碼 {last_exit}")


def main() -> None:
    parser = argparse.ArgumentParser(description="登入後自動啟動 worker 與排程器（ADR-061）")
    parser.add_argument("action", choices=["install", "uninstall", "status"])
    args = parser.parse_args()
    {"install": install, "uninstall": uninstall, "status": status}[args.action]()


if __name__ == "__main__":
    main()
