"""插件市场索引校验脚本（零第三方依赖）

校验 index.json 的结构与内容一致性，供 CI 拦截：
- JSON 合法性、顶层结构（name/version/plugins）
- 插件条目的必填字段与格式（name 合法 slug、version 语义化、updated_at 日期）
- source（插件仓库地址，必填）与 mirror（备用地址，可选）的 URL 格式
- 内容规则：name 唯一、updated_at 不得晚于今天、plugins 按 name 排序

本仓库为「索引仓库」：不托管插件源码，仅登记插件元数据与仓库地址。

用法: python scripts/validate_index.py [index.json 路径]
退出码: 0 通过 / 1 校验失败
"""

import json
import re
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlparse

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
# 归档完整性校验和：64 位小写十六进制（sha256 摘要）
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
# HTTP 归档来源特征（zip/tar 等），声明 source_sha256 时建议配合
_ARCHIVE_URL_RE = re.compile(r"\.(zip|tar|tar\.gz|tgz|tar\.bz2|tbz2|gz)(\?|/|$)", re.I)


def _err(errors: list[str], msg: str) -> None:
    errors.append(msg)


def _valid_source(value: str) -> bool:
    """source/mirror 必须是 git 仓库或 HTTP 归档 URL（本地路径不在索引仓库允许范围）

    - git 协议：`git@host:path`、`ssh://host/path`、`git+https://host/path`
    - http(s)：scheme + host 非空即可；`.git` 后缀、zip/tar 归档、带路径均合法，
      不带后缀的仓库首页式地址（如 `https://gitee.com/user/repo`）同样通过
    """
    v = value.strip()
    if v.startswith(("git@", "ssh://", "git+http://", "git+https://")):
        return True
    if v.startswith(("http://", "https://")):
        parsed = urlparse(v)
        return bool(parsed.scheme and parsed.netloc)
    return False


def validate_index(index_path: Path) -> int:
    errors: list[str] = []
    today = datetime.now(UTC).date()

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
    prev_name: str | None = None
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
            # 排序确定性：要求按 name 升序排列（减小多人 PR 的 diff 冲突）
            if prev_name is not None and name.lower() < prev_name.lower():
                _err(
                    errors,
                    f"{tag}: plugins 未按 name 排序（{prev_name} 之后出现 {name}）",
                )
            prev_name = name

        version = item.get("version")
        if isinstance(version, str) and not _VERSION_RE.match(version):
            _err(errors, f"{tag}: version 不是合法语义化版本: {version!r}")

        updated = item.get("updated_at")
        if isinstance(updated, str):
            try:
                updated_date = date.fromisoformat(updated)
            except ValueError:
                _err(errors, f"{tag}: updated_at 必须为 YYYY-MM-DD: {updated!r}")
            else:
                if updated_date > today:
                    _err(errors, f"{tag}: updated_at 晚于今天: {updated!r}")

        for field in _LIST_FIELDS:
            value = item.get(field)
            if value is None:
                continue
            if not isinstance(value, list) or not all(
                isinstance(v, str) for v in value
            ):
                _err(errors, f"{tag}: {field} 必须为字符串列表")

        source = item.get("source")
        if isinstance(source, str) and not _valid_source(source):
            _err(errors, f"{tag}: source 应为插件 git 仓库或归档 URL: {source!r}")

        mirror = item.get("mirror")
        if mirror is not None:
            if not isinstance(mirror, str) or not mirror.strip():
                _err(errors, f"{tag}: mirror 必须是非空字符串")
            elif not _valid_source(mirror):
                _err(errors, f"{tag}: mirror 应为插件 git 仓库或归档 URL: {mirror!r}")
            elif mirror.strip() == (source or "").strip():
                _err(errors, f"{tag}: mirror 与 source 相同（备用地址应不同）")

        sha = item.get("source_sha256")
        if sha is not None:
            if not isinstance(sha, str) or not _SHA256_RE.match(sha.strip()):
                _err(errors, f"{tag}: source_sha256 必须为 64 位十六进制: {sha!r}")
            elif isinstance(source, str) and not _ARCHIVE_URL_RE.search(source):
                _err(
                    errors,
                    f"{tag}: source_sha256 仅适用于 HTTP 归档来源（git 仓库自带完整性），"
                    f"source: {source!r}",
                )

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
