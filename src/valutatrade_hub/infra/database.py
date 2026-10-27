"""Синглтон-менеджер JSON-хранилища (абстракция над файлами data/*.json)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from valutatrade_hub.infra.settings import SettingsLoader


class DatabaseManager:
    """Синглтон: единая точка доступа к JSON-файлам.

    Реализован через __new__ — по тем же причинам, что и SettingsLoader.
    """

    _instance: "DatabaseManager | None" = None

    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._settings = SettingsLoader()
            cls._instance._ensure_dir()
        return cls._instance

    # --- служебное ---

    @property
    def data_dir(self) -> Path:
        return self._settings.data_dir

    def _ensure_dir(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        return self.data_dir / name

    # --- низкоуровневые операции ---

    def load(self, name: str, default: Any = None) -> Any:
        """Читает JSON-файл. Если нет или битый — возвращает default."""
        path = self._path(name)
        if not path.exists():
            return default
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return default

    def save(self, name: str, data: Any) -> None:
        """Сохраняет данные в JSON-файл (атомарно через временный файл)."""
        self._ensure_dir()
        path = self._path(name)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(path)

    # --- «чтение → модификация → запись» ---

    def update(self, name: str, mutator, default: Any = None) -> Any:
        """Читает JSON, применяет mutator(data), сохраняет и возвращает результат.

        mutator получает текущие данные (или default) и возвращает новые.
        Если mutator вернул None — запись не производится.
        """
        data = self.load(name, default)
        new_data = mutator(data)
        if new_data is not None:
            self.save(name, new_data)
            return new_data
        return data

    # --- удобные обёртки для домена ---

    @property
    def users_file(self) -> str:
        return "users.json"

    @property
    def portfolios_file(self) -> str:
        return "portfolios.json"

    @property
    def rates_file(self) -> str:
        return "rates.json"


def get_database() -> DatabaseManager:
    """Удобная функция-фасад: возвращает синглтон БД."""
    return DatabaseManager()