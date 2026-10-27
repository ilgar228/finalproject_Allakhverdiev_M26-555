"""Планировщик периодического обновления курсов."""

from __future__ import annotations

import threading

from valutatrade_hub.logging_config import get_logger
from valutatrade_hub.parser_service.updater import RatesUpdater


class Scheduler:
    """Периодический запуск RatesUpdater.run_update() в фоновом потоке.

    Реализован на threading.Timer — без внешних зависимостей.
    """

    def __init__(
        self,
        interval_seconds: int = 300,
        updater: RatesUpdater | None = None,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("Интервал должен быть положительным числом секунд")
        self.interval = int(interval_seconds)
        self.updater = updater or RatesUpdater()
        self.logger = get_logger("valutatrade.scheduler")
        self._timer: threading.Timer | None = None
        self._stopped = threading.Event()

    def start(self) -> None:
        """Запускает периодическое обновление (первое — сразу)."""
        if self._timer is not None:
            self.logger.warning("Scheduler уже запущен")
            return
        self._stopped.clear()
        self.logger.info("Scheduler started: interval=%s seconds", self.interval)
        self._run_once()

    def stop(self) -> None:
        """Останавливает планировщик."""
        self._stopped.set()
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        self.logger.info("Scheduler stopped")

    @property
    def is_running(self) -> bool:
        return self._timer is not None and not self._stopped.is_set()

    def _run_once(self) -> None:
        if self._stopped.is_set():
            return
        try:
            stats = self.updater.run_update()
            self.logger.info(
                "Scheduled update: pairs=%d errors=%d",
                stats.get("pairs_updated", 0),
                stats.get("errors", 0),
            )
        except Exception as e:  # не даём планировщику умереть
            self.logger.error(
                "Scheduled update failed: %s: %s", type(e).__name__, e
            )
        finally:
            if not self._stopped.is_set():
                self._schedule_next()

    def _schedule_next(self) -> None:
        self._timer = threading.Timer(self.interval, self._run_once)
        self._timer.daemon = True
        self._timer.start()