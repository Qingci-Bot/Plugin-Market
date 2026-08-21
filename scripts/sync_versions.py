"""插件市场索引版本自动校准脚本（零第三方依赖）

从每个插件的 `source` 仓库读取 `plugin.json` 的 `version`，与 index.json 中
登记的版本对比，不一致则更新 `version` + `updated_at`（当天），并复跑
validate_index.py 自检。供 CI 定时/手动触发（.github/workflows/sync-index.yml），
也可本地手动执行：

    python scripts/sync_versions.py [--index PATH] [--no-validate]

规则：
- 仅同步 version / updated_at 两个字段，不动其余元数据（title/source/...）
- git 来源（git@ / ssh:// / git+http(s) / .git 结尾）浅克隆后按与 Qingci 插件
  定位一致的规则找 plugin.json（仓库根，或 plugins/<name>/ 嵌套）
- HTTP 归档来源无法低成本读 plugin.json，跳过并记录
- 单个插件仓库拉取失败仅告警跳过，不阻断其余条目
- 无任何变化时不写文件（CI 据此判断是否提交，避免空提交噪音）

退出码：0 正常（含全部跳过）；非 0 仅指 index.json 无法解析/校验失败。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_INDEX_DEFAULT = REPO_ROOT / "index.json"
_GIT_SOURCE_PREFIXES = ("git@", "ssh://", "git+http://", "git+https://")
# HTTP 归档来源特征（zip/tar 等）：难以低成本读取 plugin.json，跳过
_ARCHIVE_SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".gz")


def _now() -> str:
    return datetime.now(UTC).date().isoformat()


def _is_git_source(source: str) -> bool:
    v = source.strip()
    return v.endswith(".git") or v.startswith(_GIT_SOURCE_PREFIXES)


def _is_archive_source(source: str) -> bool:
    return source.strip().lower().endswith(_ARCHIVE_SUFFIXES)


def _read_version_via_git(
    source: str, name: str, work_dir: Path, timeout: int = 120
) -> str | None:
    """浅克隆插件仓库并读取 plugin.json 的 version（读不到返回 None）

    定位规则与 Qingci PluginManager 一致：仓库根 plugin.json 优先，
    其次 plugins/<name>/ 嵌套布局。
    """
    tmp = work_dir / f"repo-{name}"
    try:
        proc = subprocess.run(
            ["git", "clone", "--depth", "1", source.strip(), str(tmp)],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"[WARN] {name}: git clone 失败（{type(e).__name__}）: {source}")
        return None
    if proc.returncode != 0:
        print(
            f"[WARN] {name}: git clone 失败: {source} -> {proc.stderr.strip()[-300:]}"
        )
        return None

    candidates = [tmp / "plugin.json", tmp / "plugins" / name / "plugin.json"]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            meta = json.loads(path.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"[WARN] {name}: plugin.json 解析失败: {path} ({type(e).__name__})")
            return None
        if not isinstance(meta, dict):
            continue
        version = meta.get("version")
        return str(version).strip() if version else None
    return None


def sync_index(index_path: Path, *, no_validate: bool = False, reader=None) -> int:
    """校准 index.json 的插件版本，返回变更条目数

    reader(source, name, work_dir) -> str | None 可注入以替换真实 git 克隆
    （测试用）；默认走 _read_version_via_git。
    """
    reader = reader or _read_version_via_git
    try:
        data = json.loads(index_path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[ERROR] index.json 无法解析: {e}")
        return -1
    plugins = data.get("plugins")
    if not isinstance(plugins, list):
        print("[ERROR] index.json 缺少 plugins 列表")
        return -1

    changed: list[str] = []
    skipped: list[str] = []
    with tempfile.TemporaryDirectory(prefix="qb-mkt-sync-") as work_dir_str:
        work_dir = Path(work_dir_str)
        for entry in plugins:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name") or "").strip()
            source = str(entry.get("source") or "").strip()
            if not name or not source:
                skipped.append(f"{name or '?'}（缺少 name/source）")
                continue
            if _is_archive_source(source):
                skipped.append(f"{name}（HTTP 归档来源，跳过）")
                continue
            if not _is_git_source(source):
                skipped.append(f"{name}（非 git 来源: {source}）")
                continue
            remote = reader(source, name, work_dir)
            if not remote:
                skipped.append(f"{name}（无法读取远端版本）")
                continue
            current = str(entry.get("version") or "")
            if remote == current:
                continue
            print(f"[SYNC] {name}: {current or '（空）'} -> {remote}")
            entry["version"] = remote
            entry["updated_at"] = _now()
            changed.append(name)

    if changed:
        index_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"[OK] 已同步 {len(changed)} 个插件版本: {', '.join(changed)}")
        if no_validate:
            return len(changed)
        validate = REPO_ROOT / "scripts" / "validate_index.py"
        rc = subprocess.call([sys.executable, str(validate), str(index_path)])
        if rc != 0:
            return 1  # 校验失败，CI 应失败
        return len(changed)

    print(f"[OK] 无版本变化，索引无需更新（跳过 {len(skipped)} 个）")
    if skipped:
        for item in skipped:
            print(f"  - 跳过: {item}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="从插件仓库自动校准市场索引版本")
    parser.add_argument(
        "--index", default=None, help="index.json 路径（默认仓库根目录）"
    )
    parser.add_argument("--no-validate", action="store_true", help="跳过校验")
    args = parser.parse_args()

    index_path = Path(args.index) if args.index else _INDEX_DEFAULT
    if not index_path.is_file():
        print(f"[ERROR] 找不到索引文件: {index_path}")
        return 1
    return sync_index(index_path, no_validate=args.no_validate)


if __name__ == "__main__":
    sys.exit(main())
