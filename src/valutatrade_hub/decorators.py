"""Декораторы для доменных операций."""

from __future__ import annotations

import functools
import inspect

from valutatrade_hub.logging_config import get_logger


def log_action(action: str, verbose: bool = False):
    """Логирует вызов функции и результат (OK/ERROR).

    Параметры:
        action: имя действия (BUY, SELL, REGISTER, LOGIN, GET_RATE).
        verbose: если True — добавляет repr аргументов и результата.

    Исключения не глотает: логирует и пробрасывает дальше.
    """
    logger = get_logger("valutatrade.actions")

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # пытаемся вытащить username/currency/amount из kwargs или аргументов
            bound = _bind_arguments(func, args, kwargs)
            username = bound.get("username") or bound.get("user_id") or "-"
            currency = bound.get("currency") or bound.get("currency_code") or "-"
            amount = bound.get("amount")
            amount_str = f"{amount:.4f}" if isinstance(amount, (int, float)) else "-"

            ctx = []
            if verbose:
                ctx.append(f"args={args!r}")
                ctx.append(f"kwargs={kwargs!r}")
            ctx_str = (" " + " ".join(ctx)) if ctx else ""

            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                logger.error(
                    "%s user='%s' currency='%s' amount=%s result=ERROR "
                    "error_type=%s error_message='%s'%s",
                    action, username, currency, amount_str,
                    type(exc).__name__, str(exc), ctx_str,
                )
                raise

            extra = ""
            if verbose and isinstance(result, dict):
                extra = f" result_data={result!r}"
            logger.info(
                "%s user='%s' currency='%s' amount=%s result=OK%s%s",
                action, username, currency, amount_str, extra, ctx_str,
            )
            return result

        return wrapper

    return decorator


def _bind_arguments(func, args, kwargs) -> dict:
    """Пытается связать аргументы функции с её параметрами (без ошибок)."""
    try:
        sig = inspect.signature(func)
        bound = sig.bind_partial(*args, **kwargs)
        return dict(bound.arguments)
    except (TypeError, ValueError):
        return {}