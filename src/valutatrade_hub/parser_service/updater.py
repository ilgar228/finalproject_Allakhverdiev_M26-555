"""Координатор обновления курсов: опрос клиентов → сохранение."""

from __future__ import annotations

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.logging_config import get_logger
from valutatrade_hub.parser_service.api_clients import (
    BaseApiClient,
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage


class RatesUpdater:
    """Опрашивает API-клиенты и сохраняет курсы в rates.json и exchange_rates.json."""

    def __init__(
        self,
        clients: list[BaseApiClient] | None = None,
        storage: RatesStorage | None = None,
        config: ParserConfig | None = None,
    ) -> None:
        self.config = config or ParserConfig()
        self.clients = clients or [
            CoinGeckoClient(self.config),
            ExchangeRateApiClient(self.config),
        ]
        self.storage = storage or RatesStorage(self.config)
        self.logger = get_logger("valutatrade.parser")

    def run_update(self, source: str | None = None) -> dict:
        """Запускает обновление курсов.

        source: "coingecko" | "exchangerate" | None (все клиенты).
        Возвращает статистику: {"pairs_updated", "history_added", "last_refresh",
        "sources": [{"name", "count"|"error"}], "errors": int}.
        """
        self.logger.info("Starting rates update...")
        allowed = self._select_clients(source)

        combined: dict[str, float] = {}
        source_map: dict[str, str] = {}
        meta_map: dict[str, dict] = {}
        per_source: list[dict] = []
        errors = 0

        for client in allowed:
            name = client.source_name
            self.logger.info("Fetching from %s...", name)
            try:
                rates = client.fetch_rates()
            except ApiRequestError as e:
                errors += 1
                self.logger.error("Failed to fetch from %s: %s", name, e)
                per_source.append({"name": name, "error": str(e)})
                continue
            except Exception as e:  # страховка от неожиданных ошибок
                errors += 1
                self.logger.error(
                    "Unexpected error from %s: %s: %s",
                    name, type(e).__name__, e,
                )
                per_source.append({"name": name, "error": str(e)})
                continue

            count = len(rates)
            self.logger.info("Fetching from %s... OK (%d rates)", name, count)
            per_source.append({"name": name, "count": count})
            for pair, rate in rates.items():
                combined[pair] = rate
                source_map[pair] = name
                meta_map[pair] = {"source": name}

        if not combined:
            self.logger.warning("No rates fetched from any source.")
            return {
                "pairs_updated": 0,
                "history_added": 0,
                "last_refresh": None,
                "sources": per_source,
                "errors": errors,
            }

        self.logger.info(
            "Writing %d rates to %s...", len(combined), self.storage.rates_path
        )
        stats = self.storage.save_all(combined, source_map, meta_map)
        stats["sources"] = per_source
        stats["errors"] = errors
        self.logger.info(
            "Update finished: pairs_updated=%d history_added=%d last_refresh=%s",
            stats["pairs_updated"], stats["history_added"], stats["last_refresh"],
        )
        return stats

    def _select_clients(self, source: str | None) -> list[BaseApiClient]:
        """Фильтрует клиентов по --source."""
        if not source:
            return self.clients
        key = source.strip().lower()
        mapping = {
            "coingecko": "CoinGecko",
            "exchangerate": "ExchangeRate-API",
            "exchangerate-api": "ExchangeRate-API",
        }
        wanted = mapping.get(key)
        if wanted is None:
            raise ValueError(
                f"Неизвестный источник '{source}'. "
                "Используйте: coingecko или exchangerate."
            )
        selected = [c for c in self.clients if c.source_name == wanted]
        if not selected:
            raise ValueError(f"Клиент для источника '{source}' не найден")
        return selected


def run_update(source: str | None = None) -> dict:
    """Удобная функция-фасад: создать RatesUpdater и запустить обновление."""
    return RatesUpdater().run_update(source=source)