"""Конфигурация Parser Service.

Ключ ExchangeRate-API читается из переменной окружения EXCHANGERATE_API_KEY,
а если её нет — из локального config_local.py (в .gitignore).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Корень проекта: .../final_project
# файл: src/valutatrade_hub/parser_service/config.py → parents[3] = final_project
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load_api_key() -> str:
    """Читает ключ: сначала env, потом config_local.py, иначе пусто."""
    env_key = os.getenv("EXCHANGERATE_API_KEY")
    if env_key:
        return env_key
    try:
        from valutatrade_hub.parser_service.config_local import (  # noqa: PLC0415
            EXCHANGERATE_API_KEY as local_key,
        )
    except ImportError:
        return ""
    return local_key


@dataclass
class ParserConfig:
    """Настройки Parser Service."""

    # Ключ ExchangeRate-API (env → config_local.py → "")
    EXCHANGERATE_API_KEY: str = field(default_factory=_load_api_key)

    # Эндпоинты
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    # Валюты
    BASE_CURRENCY: str = "USD"
    FIAT_CURRENCIES: tuple[str, ...] = ("EUR", "GBP", "RUB")
    CRYPTO_CURRENCIES: tuple[str, ...] = ("BTC", "ETH", "SOL")
    CRYPTO_ID_MAP: dict[str, str] = field(
        default_factory=lambda: {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
        }
    )

    # Пути к файлам (относительно корня проекта)
    RATES_FILE_PATH: str = "data/rates.json"
    HISTORY_FILE_PATH: str = "data/exchange_rates.json"

    # Сетевые параметры
    REQUEST_TIMEOUT: int = 10

    # --- удобные абсолютные пути ---

    @property
    def rates_file(self) -> Path:
        return PROJECT_ROOT / self.RATES_FILE_PATH

    @property
    def history_file(self) -> Path:
        return PROJECT_ROOT / self.HISTORY_FILE_PATH


def get_parser_config() -> ParserConfig:
    """Фабрика конфигурации (для удобства)."""
    return ParserConfig()