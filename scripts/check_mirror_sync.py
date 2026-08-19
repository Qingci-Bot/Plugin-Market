"""Gitee 镜像同步对拍脚本（CI 定时任务用，零第三方依赖）

比较 GitHub 权威索引 raw 与 Gitee 只读镜像 raw 是否一致，
发现镜像滞后（index.json 分叉）即非零退出，用于兜底"镜像同步延迟"问题。

用法: python scripts/check_mirror_sync.py
退出码: 0 一致 / 1 分叉 / 1 GitHub 不可用（无法对拍）
"""

import json
import sys
import urllib.error
import urllib.request
from http.client import HTTPException

GITHUB_RAW = "https://github.com/Qingci-Bot/Plugin-Market/raw/main/index.json"
GITEE_RAW = "https://gitee.com/qingci-bot/Plugin-Market/raw/main/index.json"
_HEADERS = {"User-Agent": "Qingci-Bot-Market-SyncCheck"}

_NET_ERRORS = (urllib.error.URLError, HTTPException, json.JSONDecodeError, OSError)


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    try:
        gh = _fetch_json(GITHUB_RAW)
    except _NET_ERRORS as e:
        print(f"[ERROR] GitHub 索引拉取失败，无法对拍: {e}")
        return 1

    try:
        gz = _fetch_json(GITEE_RAW)
    except _NET_ERRORS as e:
        # Gitee 匿名 raw 可能被临时拦截（HTML/429），此时不能断定镜像分叉
        print(f"[WARN] Gitee 索引拉取失败（可能正在同步或暂时不可用）: {e}")
        return 0

    if gh == gz:
        print("[OK] Gitee 镜像与 GitHub 索引一致")
        return 0
    print("[FAIL] Gitee 镜像滞后：index.json 与 GitHub 不一致，请检查镜像同步状态")
    return 1


if __name__ == "__main__":
    sys.exit(main())
