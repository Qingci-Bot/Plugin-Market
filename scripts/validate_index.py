"""插件市场索引校验脚本（零第三方依赖）

校验 index.json 的结构与内容一致性，供 CI 拦截：
- JSON 合法性、顶层结构（name/version/plugins）
- 插件条目的必填字段与格式（name 合法 slug、version 语义化、updated_at 日期）
- 与 plugins/<name>/plugin.json 的一致性（目录存在、name 匹配）

用法: python scripts/validate_index.py [index.json 路径]
退出码: 0 通过 / 1 校验失败
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# 必填字段（缺少即报错）
_REQUIRED_FIELDS = (
    "name",
    "title",
    "description",
    "version",
    "author",
    "type",
    "source",
    "updated_at",
)
# 可选但必须是 list[str] 的字段
_LIST_FIELDS = ("requirements", "tags")
# name 允许的字符集（小写字母/数字/短横线/下划线）
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_VERSION_RE = re.compile(r"^\d+\.\d+(\.\d+)?([-+][0-9A-Za-z.-]+)?$")


def _err(errors: list[str], msg: str) -> None:
    errors.append(msg)


def validate_index(index_path: Path) -> int:
    errors: list[str] = []

    try:
        # utf-8-sig 容忍 Windows 编辑器写入的 BOM
        data = json.loads(index_path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[ERROR] index.json 无法解析: {e}")
        return 1
    if not isinstance(data, dict):
        print("[ERROR] index.json 顶层必须是对象")
        return 1

    # 顶层结构
    if not isinstance(data.get("name"), str) or not data["name"].strip():
        _err(errors, "顶层缺少非空 name")
    if data.get("version") != 1:
        _err(errors, "顶层 version 必须为 1")
    plugins = data.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        _err(errors, "plugins 必须是非空列表")

    seen: set[str] = set()
    for idx, item in enumerate(plugins or []):
        if not isinstance(item, dict):
            _err(errors, f"plugins[{idx}] 必须是对象")
            continue
        tag = item.get("name") or f"plugins[{idx}]"
        for field in _REQUIRED_FIELDS:
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                _err(errors, f"{tag}: 缺少必填字段 {field}")

        name = item.get("name")
        if isinstance(name, str) and not _NAME_RE.match(name):
            _err(errors, f"{tag}: name 含非法字符（应匹配 {_NAME_RE.pattern}）")
        if isinstance(name, str):
            if name in seen:
                _err(errors, f"{tag}: name 重复")
            seen.add(name)

        version = item.get("version")
        if isinstance(version, str) and not _VERSION_RE.match(version):
            _err(errors, f"{tag}: version 不是合法语义化版本: {version!r}")

        updated = item.get("updated_at")
        if isinstance(updated, str):
            try:
                datetime.strptime(updated, "%Y-%m-%d")
            except ValueError:
                _err(errors, f"{tag}: updated_at 必须为 YYYY-MM-DD: {updated!r}")

        for field in _LIST_FIELDS:
            value = item.get(field)
            if value is None:
                continue
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                _err(errors, f"{tag}: {field} 必须为字符串列表")

        source = item.get("source")
        if isinstance(source, str) and source and "://" not in source and ".git" not in source:
            _err(errors, f"{tag}: source 应为 URL 或 .git 仓库地址: {source!r}")

        # 与插件目录一致性
        plugin_dir = REPO_ROOT / "plugins" / (name or "")
        if not plugin_dir.is_dir():
            _err(errors, f"{tag}: 缺少目录 plugins/{name or ''}")
            continue
        plugin_json = plugin_dir / "plugin.json"
        if not plugin_json.is_file():
            _err(errors, f"{tag}: 缺少 plugins/{name or ''}/plugin.json")
            continue
        try:
            meta = json.loads(plugin_json.read_text(encoding="utf-8-sig"))
            meta_name = meta.get("name") if isinstance(meta, dict) else None
            if meta_name != name:
                _err(errors, f"{tag}: plugin.json 的 name={meta_name!r} 与索引不一致")
        except (json.JSONDecodeError, OSError) as e:
            _err(errors, f"{tag}: plugin.json 无法解析: {e}")

    if errors:
        print(f"[FAIL] 校验未通过，共 {len(errors)} 个问题:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"[OK] 索引校验通过（{len(plugins or [])} 个插件）")
    return 0


def main() -> int:
    index_path = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / "index.json"
    if not index_path.is_file():
        print(f"[ERROR] 找不到索引文件: {index_path}")
        return 1
    return validate_index(index_path)


if __name__ == "__main__":
    sys.exit(main())
