import sys
from pathlib import Path

import pytest

# Добавляем корневую директорию в путь для импорта модулей
sys.path.insert(0, str(Path(__file__).parent))

pytest_plugins = ('pytest_asyncio',)


@pytest.fixture(autouse=True)
def isolate_working_directory(tmp_path, monkeypatch):
    working_dir = tmp_path / "working"
    working_dir.mkdir()
    monkeypatch.chdir(working_dir)
