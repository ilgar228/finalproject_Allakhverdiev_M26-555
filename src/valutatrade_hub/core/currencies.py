"""Иерархия валют: базовый ABC Currency и наследники Fiat/Crypto."""

from __future__ import annotations

from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError


class Currency(ABC):
    """Абстрактная валюта с общим интерфейсом."""

    def __init__(self, name: str, code: str) -> None:
        self._name = ""
        self._code = ""
        self.name = name
        self.code = code

    # --- валидация и свойства ---

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя валюты не может быть пустым")
        self._name = value.strip()

    @property
    def code(self) -> str:
        return self._code

    @code.setter
    def code(self, value: str) -> None:
        if not isinstance(value, str):
            raise ValueError("Код валюты должен быть строкой")
        code = value.strip().upper()
        if not (2 <= len(code) <= 5):
            raise ValueError("Код валюты должен содержать 2–5 символов")
        if " " in code:
            raise ValueError("Код валюты не должен содержать пробелов")
        self._code = code

    # --- интерфейс ---

    @abstractmethod
    def get_display_info(self) -> str:
        """Строковое представление для UI/логов."""
        raise NotImplementedError


class FiatCurrency(Currency):
    """Фиатная валюта с указанием страны/зоны эмиссии."""

    def __init__(self, name: str, code: str, issuing_country: str) -> None:
        super().__init__(name=name, code=code)
        if not isinstance(issuing_country, str) or not issuing_country.strip():
            raise ValueError("Страна эмиссии не может быть пустой")
        self.issuing_country = issuing_country.strip()

    def get_display_info(self) -> str:
        return (
            f"[FIAT] {self.code} — {self.name} "
            f"(Issuing: {self.issuing_country})"
        )


class CryptoCurrency(Currency):
    """Криптовалюта с алгоритмом и рыночной капитализацией."""

    def __init__(
        self,
        name: str,
        code: str,
        algorithm: str,
        market_cap: float,
    ) -> None:
        super().__init__(name=name, code=code)
        if not isinstance(algorithm, str) or not algorithm.strip():
            raise ValueError("Алгоритм не может быть пустым")
        if not isinstance(market_cap, (int, float)) or market_cap < 0:
            raise ValueError(
                "Рыночная капитализация должна быть неотрицательным числом"
            )
        self.algorithm = algorithm.strip()
        self.market_cap = float(market_cap)

    def get_display_info(self) -> str:
        mcap = f"{self.market_cap:.2e}".replace("e+", "e")
        return (
            f"[CRYPTO] {self.code} — {self.name} "
            f"(Algo: {self.algorithm}, MCAP: {mcap})"
        )


# --- реестр валют ---

_REGISTRY: dict[str, Currency] = {
    "USD": FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": FiatCurrency("Euro", "EUR", "Eurozone"),
    "RUB": FiatCurrency("Russian Ruble", "RUB", "Russia"),
    "BTC": CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("Ethereum", "ETH", "Ethash", 4.0e11),
}


def get_currency(code: str) -> Currency:
    """Возвращает объект валюты по коду или кидает CurrencyNotFoundError."""
    if not isinstance(code, str):
        raise CurrencyNotFoundError(str(code))
    key = code.strip().upper()
    currency = _REGISTRY.get(key)
    if currency is None:
        raise CurrencyNotFoundError(key)
    return currency


def list_currencies() -> list[Currency]:
    """Возвращает список всех зарегистрированных валют (для help)."""
    return list(_REGISTRY.values())