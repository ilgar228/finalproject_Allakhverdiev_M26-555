"""Синглтон-загрузчик конфигурации проекта."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

# Корень проекта: .../final_project
# файл: src/valutatrade_hub/infra/settings.py → parents[3] = final_project
PROJECT_ROOT = Path(__file__).resolve().parents[3]
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"

_DEFAULTS: dict[str, Any] = {
    "data_dir": "data",
    "rates_ttl_seconds": 300,
    "default_base_currency": "USD",
    "log_file": "logs/actions.log",
    "log_level": "INFO",
    "log_format": "text",
    "log_max_bytes": 1_048_576,
    "log_backup_count": 3,
}


class SettingsLoader:
    """Синглтон: единственный экземпляр конфигурации на процесс.

    Реализован через __new__ — проще и читабельнее метакласса,
    а для нашей задачи (один класс-синглтон) этого достаточно.
    """

    _instance: "SettingsLoader | None" = None

    def __new__(cls) -> "SettingsLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
            cls._instance._data = {}
            cls._instance.reload()
        return cls._instance

    def reload(self) -> None:
        """Перечитывает конфигурацию из pyproject.toml (секция [tool.valutatrade])."""
        data = dict(_DEFAULTS)
        try:
            with PYPROJECT_PATH.open("rb") as f:
                pyproject = tomllib.load(f)
            section = pyproject.get("tool", {}).get("valutatrade", {})
            if isinstance(section, dict):
                data.update(section)
        except (FileNotFoundError, tomllib.TOMLDecodeError):
            # нет pyproject или он битый — работаем на дефолтах
            pass
        self._data = data
        self._loaded = True

    def get(self, key: str, default: Any = None) -> Any:
        """Возвращает значение по ключу или default."""
        return self._data.get(key, default)

    # --- удобные производные свойства ---

    @property
    def data_dir(self) -> Path:
        path = Path(self.get("data_dir", "data"))
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def rates_ttl_seconds(self) -> int:
        return int(self.get("rates_ttl_seconds", 300))

    @property
    def default_base_currency(self) -> str:
        return str(self.get("default_base_currency", "USD")).upper()

    @property
    def log_file(self) -> Path:
        path = Path(self.get("log_file", "logs/actions.log"))
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def log_level(self) -> str:
        return str(self.get("log_level", "INFO")).upper()

    @property
    def log_format(self) -> str:
        return str(self.get("log_format", "text")).lower()

    @property
    def log_max_bytes(self) -> int:
        return int(self.get("log_max_bytes", 1_048_576))

    @property
    def log_backup_count(self) -> int:
        return int(self.get("log_backup_count", 3))


def get_settings() -> SettingsLoader:
    """Удобная функция-фасад: возвращает синглтон настроек."""
    return SettingsLoader()