"""スモークテスト: main.run() が成果物を生成し DBに保存されることを確認する。"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from src.main import run
from src.shared.config import INPUT_DIR


@pytest.fixture()
def tmp_dirs(tmp_path: Path):
    output = tmp_path / "output"
    db = tmp_path / "db" / "test.db"
    return output, db


def test_run_creates_output_files(tmp_dirs):
    output, db = tmp_dirs
    input_path = INPUT_DIR / "sample_events.json"

    record = run(input_path, output, db)

    assert record.status == "completed"
    assert record.event_id  # 何かIDが入っている

    # 成果物ファイルが存在する
    assert Path(record.script_path).exists()
    assert Path(record.article_path).exists()
    assert Path(record.video_payload_path).exists()


def test_script_json_is_valid(tmp_dirs):
    output, db = tmp_dirs
    input_path = INPUT_DIR / "sample_events.json"
    record = run(input_path, output, db)

    data = json.loads(Path(record.script_path).read_text())
    assert "title" in data
    assert "sections" in data
    assert isinstance(data["sections"], list)
    assert len(data["sections"]) > 0


def test_article_markdown_has_heading(tmp_dirs):
    output, db = tmp_dirs
    input_path = INPUT_DIR / "sample_events.json"
    record = run(input_path, output, db)

    md = Path(record.article_path).read_text(encoding="utf-8")
    assert md.startswith("# ")


def test_video_payload_has_scenes(tmp_dirs):
    output, db = tmp_dirs
    input_path = INPUT_DIR / "sample_events.json"
    record = run(input_path, output, db)

    data = json.loads(Path(record.video_payload_path).read_text())
    assert "scenes" in data
    assert len(data["scenes"]) >= 3  # intro + sections + outro


def test_job_saved_to_db(tmp_dirs):
    output, db = tmp_dirs
    input_path = INPUT_DIR / "sample_events.json"
    record = run(input_path, output, db)

    conn = sqlite3.connect(str(db))
    rows = conn.execute("SELECT * FROM jobs WHERE id = ?", (record.id,)).fetchall()
    conn.close()

    assert len(rows) == 1
    assert rows[0][2] == "completed"  # status column
