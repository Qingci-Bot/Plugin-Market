"""插件市场索引条目维护脚本（零第三方依赖）

按插件名更新 index.json 中的条目：
- `--version` 必填，更新版本号；`updated_at` 默认取当天，可用 `--updated-at` 覆盖
- 其余字段（title/description/author/icon/homepage/source/mirror/python_requires 等）
  仅在显式传参时更新，未传字段保持不变
- 更新后自动调用 validate_index.py 做自检（可用 `--no-validate` 跳过）

用法: python scripts/bump_index.py <name> --version 1.5.0 [--index PATH] [选项]
示例: python scripts/bump_index.py hello --version 1.5.0 --description "新增 xxx 能力"
"""

import argparse
import json
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# 支持更新的字段名（argparse 选项名 -> index.json 字段名）
_FIELD_OPTIONS = {
    "title": "title",
    "description": "description",
    "author": "author",
    "icon": "icon",
    "homepage": "homepage",
    "source": "source",
    "mirror": "mirror",
    "python_requires": "python_requires",
    "source_sha256": "source_sha256",
}


def _now() -> str:
    return datetime.now(UTC).date().isoformat()


def bump_index(name: str, version: str, updated_at: str, index_path: Path, options: dict) -> int:
    try:
        data = json.loads(index_path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[ERROR] index.json 无法解析: {e}")
        return 1

    plugins = data.get("plugins")
    if not isinstance(plugins, list):
        print("[ERROR] index.json 缺少 plugins 列表")
        return 1

    entry = next((p for p in plugins if isinstance(p, dict) and p.get("name") == name), None)
    if entry is None:
        known = ", ".join(str(p.get("name")) for p in plugins if isinstance(p, dict))
        print(f"[ERROR] 找不到插件 {name!r}；现有: {known or '（空）'}")
        return 1

    entry["version"] = version
    entry["updated_at"] = updated_at
    for opt, field in _FIELD_OPTIONS.items():
        if options.get(opt) is not None:
            entry[field] = options[opt]
    for tag in options.get("tags") or []:
        tags = entry.setdefault("tags", [])
        if tag not in tags:
            tags.append(tag)
    for req in options.get("requirements") or []:
        reqs = entry.setdefault("requirements", [])
        if req not in reqs:
            reqs.append(req)

    index_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"[OK] 已更新 {name}: version={version} updated_at={updated_at}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="更新插件市场索引条目")
    parser.add_argument("name", help="插件名（index.json 中的 name）")
    parser.add_argument("--version", required=True, help="新版本号（如 1.5.0）")
    parser.add_argument("--updated-at", default=None, help="更新日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--index", default=None, help="index.json 路径（默认仓库根目录）")
    parser.add_argument("--no-validate", action="store_true", help="跳过校验")
    for opt in _FIELD_OPTIONS:
        parser.add_argument(f"--{opt}", default=None, help=f"更新字段 {opt}")
    parser.add_argument("--tag", action="append", default=None, help="追加标签（可多次）")
    parser.add_argument("--requirement", action="append", default=None, help="追加依赖（可多次）")
    args = parser.parse_args()

    index_path = Path(args.index) if args.index else REPO_ROOT / "index.json"
    if not index_path.is_file():
        print(f"[ERROR] 找不到索引文件: {index_path}")
        return 1

    updated_at = args.updated_at or _now()
    if args.updated_at:
        try:
            date.fromisoformat(args.updated_at)
        except ValueError:
            print(f"[ERROR] updated_at 必须为 YYYY-MM-DD: {args.updated_at!r}")
            return 1

    options = {
        "title": args.title,
        "description": args.description,
        "author": args.author,
        "icon": args.icon,
        "homepage": args.homepage,
        "source": args.source,
        "mirror": args.mirror,
        "python_requires": args.python_requires,
        "tags": args.tag,
        "requirements": args.requirement,
    }
    rc = bump_index(args.name, args.version, updated_at, index_path, options)
    if rc != 0:
        return rc

    if not args.no_validate:
        validate = REPO_ROOT / "scripts" / "validate_index.py"
        return subprocess.call([sys.executable, str(validate), str(index_path)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
