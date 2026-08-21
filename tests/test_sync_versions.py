"""sync_versions.py 单元测试（注入 reader，不触网/不克隆）"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import sync_versions as sync


def _write_index(tmp_path: Path, version: str, updated_at: str = "2026-08-19") -> Path:
    index = {
        "name": "Qingci-Bot 插件市场",
        "version": 1,
        "plugins": [
            {
                "name": "hello",
                "title": "Hello 示例插件",
                "description": "演示插件",
                "version": version,
                "author": "Qingci-Bot",
                "type": "sdk",
                "source": "https://github.com/Qingci-Bot/hello.git",
                "updated_at": updated_at,
            }
        ],
    }
    path = tmp_path / "index.json"
    path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    return path


def _fake_reader(version: str):
    def reader(source: str, name: str, work_dir: Path):
        return version

    return reader


def test_sync_updates_version_and_updated_at(tmp_path, monkeypatch):
    index_path = _write_index(tmp_path, "1.4.0")
    # 避免子进程跑 validate，这里只验证脚本自身的更新逻辑
    changed = sync.sync_index(
        index_path, no_validate=True, reader=_fake_reader("1.5.0")
    )
    assert changed == 1

    data = json.loads(index_path.read_text(encoding="utf-8"))
    entry = data["plugins"][0]
    assert entry["version"] == "1.5.0"
    assert entry["updated_at"] == datetime.now(UTC).date().isoformat()


def test_sync_no_change_keeps_file_untouched(tmp_path):
    index_path = _write_index(tmp_path, "1.4.0")
    before = index_path.read_text(encoding="utf-8")
    changed = sync.sync_index(
        index_path, no_validate=True, reader=_fake_reader("1.4.0")
    )
    assert changed == 0
    assert index_path.read_text(encoding="utf-8") == before


def test_sync_skips_archive_source(tmp_path, capsys):
    index_path = _write_index(tmp_path, "1.4.0")
    data = json.loads(index_path.read_text(encoding="utf-8"))
    data["plugins"][0]["source"] = "https://example.com/plugin.zip"
    index_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    changed = sync.sync_index(
        index_path, no_validate=True, reader=_fake_reader("9.9.9")
    )
    assert changed == 0
    out = capsys.readouterr().out
    assert "HTTP 归档来源" in out
