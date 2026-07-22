import json
from pathlib import Path

import pytest
from database import Database


def test_read_missing_file_returns_empty_dict(tmp_path: Path) -> None:
    db = Database(tmp_path / "missing.json")
    assert db.read() == {}


def test_write_then_read_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "db.json"
    db = Database(path)
    payload = {"a": 1, "nested": {"b": [2, 3]}}

    db.write(payload)
    assert json.loads(path.read_text(encoding="utf-8")) == payload
    assert db.read() == payload


def test_read_invalid_json_returns_empty_dict(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not-json", encoding="utf-8")
    assert Database(path).read() == {}


def test_write_rejects_non_jsonable_without_touching_file(tmp_path: Path) -> None:
    path = tmp_path / "db.json"
    path.write_text('{"ok": true}', encoding="utf-8")
    db = Database(path)

    with pytest.raises(TypeError):
        db.write({"bad": object()})

    assert json.loads(path.read_text(encoding="utf-8")) == {"ok": True}
