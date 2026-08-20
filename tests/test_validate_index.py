"""validate_index.py 的单元测试（pytest）

通过 subprocess 或直接 import 脚本模块验证校验逻辑。
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import validate_index


def _valid_index() -> dict:
    return {
        "name": "Qingci-Bot 插件市场",
        "version": 1,
        "plugins": [
            {
                "name": "hello",
                "title": "Hello 示例",
                "description": "示例插件",
                "version": "1.2.0",
                "author": "tester",
                "type": "sdk",
                "source": "https://github.com/author/hello.git",
                "mirror": "https://gitee.com/author/hello",
                "tags": ["demo"],
                "requirements": ["qingci-plugin-sdk>=1.0"],
                "updated_at": "2026-08-19",
            }
        ],
    }


@pytest.fixture
def index_file(tmp_path: Path) -> Path:
    path = tmp_path / "index.json"
    path.write_text(json.dumps(_valid_index(), ensure_ascii=False), encoding="utf-8")
    return path


# ---------- 通过用例 ----------


def test_valid_index_passes(index_file: Path):
    assert validate_index.validate_index(index_file) == 0


def test_mirror_http_without_git_suffix_passes(index_file: Path):
    """mirror 允许不带 .git 后缀的 http(s) 地址（修复误报回归）"""
    data = json.loads(index_file.read_text(encoding="utf-8"))
    data["plugins"][0]["source"] = "https://gitee.com/user/repo"
    index_file.write_text(json.dumps(data), encoding="utf-8")
    assert validate_index.validate_index(index_file) == 0


def test_git_protocol_source_passes(index_file: Path):
    data = json.loads(index_file.read_text(encoding="utf-8"))
    data["plugins"][0]["source"] = "git@github.com:author/hello.git"
    index_file.write_text(json.dumps(data), encoding="utf-8")
    assert validate_index.validate_index(index_file) == 0


# ---------- 结构/字段错误 ----------


def test_missing_required_field(index_file: Path):
    data = json.loads(index_file.read_text(encoding="utf-8"))
    del data["plugins"][0]["source"]
    index_file.write_text(json.dumps(data), encoding="utf-8")
    assert validate_index.validate_index(index_file) == 1


def test_empty_plugins_rejected(index_file: Path):
    data = json.loads(index_file.read_text(encoding="utf-8"))
    data["plugins"] = []
    index_file.write_text(json.dumps(data), encoding="utf-8")
    assert validate_index.validate_index(index_file) == 1


def test_duplicate_name_rejected(index_file: Path):
    data = json.loads(index_file.read_text(encoding="utf-8"))
    dup = dict(data["plugins"][0])
    dup["name"] = "hello"
    data["plugins"].append(dup)
    index_file.write_text(json.dumps(data), encoding="utf-8")
    assert validate_index.validate_index(index_file) == 1


def test_invalid_name_rejected(index_file: Path):
    data = json.loads(index_file.read_text(encoding="utf-8"))
    data["plugins"][0]["name"] = "Hello-Plugin"
    index_file.write_text(json.dumps(data), encoding="utf-8")
    assert validate_index.validate_index(index_file) == 1


def test_invalid_version_rejected(index_file: Path):
    data = json.loads(index_file.read_text(encoding="utf-8"))
    data["plugins"][0]["version"] = "1.0.0.0.1"
    index_file.write_text(json.dumps(data), encoding="utf-8")
    assert validate_index.validate_index(index_file) == 1


# ---------- 日期规则 ----------


def test_future_updated_at_rejected(index_file: Path):
    data = json.loads(index_file.read_text(encoding="utf-8"))
    data["plugins"][0]["updated_at"] = "2999-01-01"
    index_file.write_text(json.dumps(data), encoding="utf-8")
    assert validate_index.validate_index(index_file) == 1


def test_bad_updated_at_format_rejected(index_file: Path):
    data = json.loads(index_file.read_text(encoding="utf-8"))
    data["plugins"][0]["updated_at"] = "2026/08/19"
    index_file.write_text(json.dumps(data), encoding="utf-8")
    assert validate_index.validate_index(index_file) == 1


# ---------- 地址规则 ----------


def test_local_path_source_rejected(index_file: Path):
    data = json.loads(index_file.read_text(encoding="utf-8"))
    data["plugins"][0]["source"] = "D:\\plugin\\hello"
    index_file.write_text(json.dumps(data), encoding="utf-8")
    assert validate_index.validate_index(index_file) == 1


def test_mirror_equal_source_rejected(index_file: Path):
    data = json.loads(index_file.read_text(encoding="utf-8"))
    data["plugins"][0]["mirror"] = data["plugins"][0]["source"]
    index_file.write_text(json.dumps(data), encoding="utf-8")
    assert validate_index.validate_index(index_file) == 1


def test_invalid_mirror_rejected(index_file: Path):
    data = json.loads(index_file.read_text(encoding="utf-8"))
    data["plugins"][0]["mirror"] = "not-a-url"
    index_file.write_text(json.dumps(data), encoding="utf-8")
    assert validate_index.validate_index(index_file) == 1


# ---------- source_sha256 归档校验和 ----------


def test_source_sha256_archive_passes(index_file: Path):
    """HTTP 归档来源 + 合法 64 位 sha256 通过"""
    data = json.loads(index_file.read_text(encoding="utf-8"))
    entry = data["plugins"][0]
    entry["source"] = "https://example.com/releases/hello-v1.2.0.zip"
    entry["source_sha256"] = "a" * 64
    index_file.write_text(json.dumps(data), encoding="utf-8")
    assert validate_index.validate_index(index_file) == 0


def test_source_sha256_bad_format_rejected(index_file: Path):
    """非 64 位十六进制的 sha256 被拒绝"""
    data = json.loads(index_file.read_text(encoding="utf-8"))
    entry = data["plugins"][0]
    entry["source"] = "https://example.com/releases/hello-v1.2.0.zip"
    entry["source_sha256"] = "zz" + "a" * 62
    index_file.write_text(json.dumps(data), encoding="utf-8")
    assert validate_index.validate_index(index_file) == 1


def test_source_sha256_on_git_source_rejected(index_file: Path):
    """git 仓库来源声明 source_sha256 被拒绝（git 自带完整性）"""
    data = json.loads(index_file.read_text(encoding="utf-8"))
    entry = data["plugins"][0]
    entry["source"] = "https://github.com/author/hello.git"
    entry["source_sha256"] = "b" * 64
    index_file.write_text(json.dumps(data), encoding="utf-8")
    assert validate_index.validate_index(index_file) == 1


# ---------- 排序规则 ----------


def test_unsorted_plugins_rejected(index_file: Path):
    data = json.loads(index_file.read_text(encoding="utf-8"))
    second = dict(data["plugins"][0])
    second["name"] = "aaa"
    second["source"] = "https://github.com/a/aaa.git"
    data["plugins"] = [data["plugins"][0], second]  # hello 排在 aaa 前 = 未排序
    index_file.write_text(json.dumps(data), encoding="utf-8")
    assert validate_index.validate_index(index_file) == 1


def test_sorted_plugins_pass(index_file: Path):
    data = json.loads(index_file.read_text(encoding="utf-8"))
    second = dict(data["plugins"][0])
    second["name"] = "zzz"
    second["source"] = "https://github.com/z/zzz.git"
    data["plugins"] = [data["plugins"][0], second]  # hello < zzz = 有序
    index_file.write_text(json.dumps(data), encoding="utf-8")
    assert validate_index.validate_index(index_file) == 0


def test_own_index_file_passes():
    """仓库自带 index.json 应始终通过"""
    assert validate_index.validate_index(REPO_ROOT / "index.json") == 0
