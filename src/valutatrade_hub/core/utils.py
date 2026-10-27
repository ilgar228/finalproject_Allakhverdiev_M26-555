"""Вспомогательные функции: валидация валют, конвертация, JSON-обёртки."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.infra.database import get_database

# --- валидация валютных кодов ---

def validate_currency_code(code: str) -> str:
    """Нормализует код валюты и проверяет, что он известен.

    Возвращает код в верхнем регистре. Кидает CurrencyNotFoundError для неизвестных.
    """
    currency = get_currency(code)  # сам нормализует и кидает при неизвестном
    return currency.code


# --- конвертация ---

RateProvider = Callable[[str, str], float]


def convert(
    amount: float,
    from_code: str,
    to_code: str,
    rate_provider: RateProvider,
) -> float:
    """Конвертирует amount из from_code в to_code через rate_provider.

    rate_provider(from_code, to_code) должен вернуть курс (сколько to за 1 from).
    """
    if not isinstance(amount, (int, float)) or isinstance(amount, bool):
        raise TypeError("Сумма должна быть числом")
    src = validate_currency_code(from_code)
    dst = validate_currency_code(to_code)
    if src == dst:
        return float(amount)
    rate = rate_provider(src, dst)
    return float(amount) * rate


# --- JSON-обёртки (тонкий слой над DatabaseManager) ---
# Оставлены для обратной совместимости и удобства в тестах/скриптах.

def load_users() -> list[dict]:
    return get_database().load(get_database().users_file, [])


def save_users(users: list[dict]) -> None:
    get_database().save(get_database().users_file, users)


def load_portfolios() -> list[dict]:
    return get_database().load(get_database().portfolios_file, [])


def save_portfolios(portfolios: list[dict]) -> None:
    get_database().save(get_database().portfolios_file, portfolios)


def _default_rates() -> dict[str, Any]:
    """Пустой снимок в новом формате (Parser Service заполнит его)."""
    return {"pairs": {}, "last_refresh": None}


def load_rates() -> dict[str, Any]:
    """Курсы валют. Если rates.json нет — дефолтные значения-заглушки."""
    return get_database().load(get_database().rates_file, _default_rates())


def save_rates(rates: dict[str, Any]) -> None:
    get_database().save(get_database().rates_file, rates)


# --- совместимость со старым API ---

def ensure_data_dir() -> None:
    """Создаёт data/ (делегирует в DatabaseManager)."""
    get_database()._ensure_dir()


def load_json(path: Path, default: Any = None) -> Any:
    """Совместимость: читает JSON по абсолютному пути.

    Оставлено для старых скриптов; в новом коде используйте DatabaseManager.
    """
    import json

    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path: Path, data: Any) -> None:
    """Совместимость: пишет JSON по абсолютному пути."""
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)