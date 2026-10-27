"""Хранилище Parser Service: снимок rates.json и история exchange_rates.json."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from valutatrade_hub.infra.settings import get_settings
from valutatrade_hub.parser_service.config import ParserConfig


def _utc_now_iso() -> str:
    """Текущее UTC-время в ISO 8601 с 'Z' (например, 2025-10-10T12:00:00Z)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write_json(path: Path, data) -> None:
    """Атомарная запись JSON: пишем в .tmp, потом replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


class RatesStorage:
    """Операции чтения/записи для rates.json и exchange_rates.json."""

    def __init__(self, config: ParserConfig | None = None) -> None:
        self.config = config or ParserConfig()
        self.rates_path = self.config.rates_file
        self.history_path = self.config.history_file

    # --- rates.json (снимок) ---

    def load_snapshot(self) -> dict:
        """Возвращает текущий снимок rates.json (или пустую структуру)."""
        data = _read_json(self.rates_path, default=None)
        if not isinstance(data, dict):
            return {"pairs": {}, "last_refresh": None}
        # поддержка старого формата: плоский словарь {"BTC_USD": {...}}
        if "pairs" not in data:
            pairs = {
                k: v
                for k, v in data.items()
                if isinstance(v, dict) and "rate" in v
            }
            last_refresh = data.get("last_refresh")
            return {"pairs": pairs, "last_refresh": last_refresh}
        data.setdefault("pairs", {})
        data.setdefault("last_refresh", None)
        return data

    def save_snapshot(
        self, updates: dict[str, float], source_map: dict[str, str]
    ) -> dict:
        """Обновляет снимок rates.json: только более свежие значения «побеждают».

        updates: {"BTC_USD": 79800.0, ...}
        source_map: {"BTC_USD": "CoinGecko", ...}
        Возвращает новый снимок.
        """
        snapshot = self.load_snapshot()
        pairs = snapshot["pairs"]
        now_iso = _utc_now_iso()

        for pair, rate in updates.items():
            if not isinstance(rate, (int, float)) or rate <= 0:
                continue
            # всегда перезаписываем — этот апдейт самый свежий
            pairs[pair] = {
                "rate": float(rate),
                "updated_at": now_iso,
                "source": source_map.get(pair, "unknown"),
            }
        snapshot["pairs"] = pairs
        snapshot["last_refresh"] = now_iso
        _atomic_write_json(self.rates_path, snapshot)
        return snapshot

    # --- exchange_rates.json (история) ---

    def load_history(self) -> list[dict]:
        data = _read_json(self.history_path, default=[])
        return data if isinstance(data, list) else []

    def append_history(
        self,
        updates: dict[str, float],
        source_map: dict[str, str],
        meta_map: dict[str, dict] | None = None,
    ) -> int:
        """Добавляет записи в историю. Возвращает количество добавленных.

        id = <FROM>_<TO>_<ISO-UTC timestamp>, дубликаты не добавляются.
        """
        history = self.load_history()
        existing_ids = {rec.get("id") for rec in history if isinstance(rec, dict)}
        now_iso = _utc_now_iso()
        added = 0
        meta_map = meta_map or {}

        for pair, rate in updates.items():
            if not isinstance(rate, (int, float)) or rate <= 0:
                continue
            if "_" not in pair:
                continue
            src_code, dst_code = pair.split("_", 1)
            record_id = f"{src_code}_{dst_code}_{now_iso}"
            if record_id in existing_ids:
                continue
            record = {
                "id": record_id,
                "from_currency": src_code,
                "to_currency": dst_code,
                "rate": float(rate),
                "timestamp": now_iso,
                "source": source_map.get(pair, "unknown"),
                "meta": meta_map.get(pair, {}),
            }
            history.append(record)
            existing_ids.add(record_id)
            added += 1

        if added:
            _atomic_write_json(self.history_path, history)
        return added

    def save_all(
        self,
        updates: dict[str, float],
        source_map: dict[str, str],
        meta_map: dict[str, dict] | None = None,
    ) -> dict:
        """Сохраняет и снимок, и историю. Возвращает статистику."""
        snapshot = self.save_snapshot(updates, source_map)
        added = self.append_history(updates, source_map, meta_map)
        return {
            "pairs_updated": len(updates),
            "history_added": added,
            "last_refresh": snapshot.get("last_refresh"),
        }


def get_storage() -> RatesStorage:
    """Фабрика хранилища (удобно для CLI/updater)."""
    # на будущее: можно подмешать TTL из SettingsLoader
    _ = get_settings()
    return RatesStorage()