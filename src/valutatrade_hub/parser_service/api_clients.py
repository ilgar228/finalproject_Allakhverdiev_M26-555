"""Клиенты внешних API: CoinGecko (крипто) и ExchangeRate-API (фиат)."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig


class BaseApiClient(ABC):
    """Базовый класс API-клиента."""

    source_name: str = "Unknown"

    def __init__(self, config: ParserConfig | None = None) -> None:
        self.config = config or ParserConfig()

    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        """Возвращает словарь {'BTC_USD': rate, ...}."""
        raise NotImplementedError


class CoinGeckoClient(BaseApiClient):
    """Клиент CoinGecko: криптовалюты к USD."""

    source_name = "CoinGecko"

    def fetch_rates(self) -> dict[str, float]:
        ids = ",".join(
            self.config.CRYPTO_ID_MAP[c]
            for c in self.config.CRYPTO_CURRENCIES
            if c in self.config.CRYPTO_ID_MAP
        )
        if not ids:
            return {}
        vs = self.config.BASE_CURRENCY.lower()
        params = {"ids": ids, "vs_currencies": vs}

        try:
            response = requests.get(
                self.config.COINGECKO_URL,
                params=params,
                timeout=self.config.REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException as e:
            raise ApiRequestError(f"CoinGecko: сетевая ошибка ({e})") from e

        if response.status_code != 200:
            raise ApiRequestError(
                f"CoinGecko: HTTP {response.status_code} ({response.text[:200]})"
            )

        try:
            data = response.json()
        except ValueError as e:
            raise ApiRequestError("CoinGecko: некорректный JSON в ответе") from e

        result: dict[str, float] = {}
        for code, cg_id in self.config.CRYPTO_ID_MAP.items():
            if code not in self.config.CRYPTO_CURRENCIES:
                continue
            entry = data.get(cg_id)
            if not isinstance(entry, dict):
                continue
            rate = entry.get(vs)
            if isinstance(rate, (int, float)) and rate > 0:
                result[f"{code}_{self.config.BASE_CURRENCY}"] = float(rate)
        return result


class ExchangeRateApiClient(BaseApiClient):
    """Клиент ExchangeRate-API: фиатные валюты к базовой (USD)."""

    source_name = "ExchangeRate-API"

    def fetch_rates(self) -> dict[str, float]:
        key = self.config.EXCHANGERATE_API_KEY
        if not key:
            raise ApiRequestError(
                "ExchangeRate-API: ключ не задан (EXCHANGERATE_API_KEY)"
            )

        url = f"{self.config.EXCHANGERATE_API_URL}/{key}/latest/"
        url += self.config.BASE_CURRENCY

        try:
            response = requests.get(url, timeout=self.config.REQUEST_TIMEOUT)
        except requests.exceptions.RequestException as e:
            raise ApiRequestError(f"ExchangeRate-API: сетевая ошибка ({e})") from e

        if response.status_code != 200:
            raise ApiRequestError(
                f"ExchangeRate-API: HTTP {response.status_code}"
            )

        try:
            data = response.json()
        except ValueError as e:
            raise ApiRequestError(
                "ExchangeRate-API: некорректный JSON в ответе"
            ) from e

        if data.get("result") != "success":
            reason = data.get("error-type") or "unknown error"
            raise ApiRequestError(f"ExchangeRate-API: {reason}")

                # v6 отдаёт conversion_rates, некоторые версии — rates
        rates = data.get("conversion_rates") or data.get("rates") or {}
        result: dict[str, float] = {}
        for code in self.config.FIAT_CURRENCIES:
            rate = rates.get(code)
            if isinstance(rate, (int, float)) and rate > 0:
                # API возвращает: 1 BASE = rate CODE, нам нужен CODE -> BASE
                result[f"{code}_{self.config.BASE_CURRENCY}"] = 1.0 / float(rate)
        return result


def fetch_all(config: ParserConfig | None = None) -> dict[str, dict]:
    """Опрашивает оба клиента. Возвращает {pair: {rate, source, error?}}.

    Отказоустойчивость: если один клиент упал, второй всё равно опрашивается.
    """
    cfg = config or ParserConfig()
    clients = [CoinGeckoClient(cfg), ExchangeRateApiClient(cfg)]
    out: dict[str, dict] = {}

    for client in clients:
        started = time.monotonic()
        try:
            rates = client.fetch_rates()
        except ApiRequestError as e:
            out[client.source_name] = {"error": str(e), "rates": {}}
            continue
        ms = int((time.monotonic() - started) * 1000)
        out[client.source_name] = {
            "rates": rates,
            "request_ms": ms,
            "count": len(rates),
        }
    return out