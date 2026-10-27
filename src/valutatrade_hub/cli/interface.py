"""Командный интерфейс платформы valutatrade."""

from __future__ import annotations

import argparse
import sys
import time

from prettytable import PrettyTable

from valutatrade_hub.core import usecases
from valutatrade_hub.core.currencies import list_currencies
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
    ValutaTradeError,
)


def _build_parser() -> argparse.ArgumentParser:
    """Собирает парсер команд CLI."""
    parser = argparse.ArgumentParser(
        prog="valutatrade",
        description="Платформа для отслеживания и симуляции торговли валютами",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_reg = sub.add_parser("register", help="Зарегистрировать нового пользователя")
    p_reg.add_argument("--username", required=True)
    p_reg.add_argument("--password", required=True)

    p_log = sub.add_parser("login", help="Войти в систему")
    p_log.add_argument("--username", required=True)
    p_log.add_argument("--password", required=True)

    sub.add_parser("logout", help="Выйти из системы")

    p_sp = sub.add_parser("show-portfolio", help="Показать портфель")
    p_sp.add_argument("--base", default="USD", help="Базовая валюта (по умолчанию USD)")

    p_buy = sub.add_parser("buy", help="Купить валюту")
    p_buy.add_argument("--currency", required=True)
    p_buy.add_argument("--amount", required=True, type=float)

    p_sell = sub.add_parser("sell", help="Продать валюту")
    p_sell.add_argument("--currency", required=True)
    p_sell.add_argument("--amount", required=True, type=float)

    p_rate = sub.add_parser("get-rate", help="Получить курс валюты")
    p_rate.add_argument("--from", dest="from_currency", required=True)
    p_rate.add_argument("--to", dest="to_currency", required=True)

    sub.add_parser("list-currencies", help="Показать поддерживаемые валюты")

    p_upd = sub.add_parser("update-rates", help="Обновить курсы из внешних API")
    p_upd.add_argument(
        "--source",
        default=None,
        help="coingecko | exchangerate (по умолчанию — все)",
    )

    p_show = sub.add_parser("show-rates", help="Показать курсы из кеша")
    p_show.add_argument("--currency", default=None)
    p_show.add_argument("--top", type=int, default=None)
    p_show.add_argument("--base", default=None)

    p_sched = sub.add_parser("start-scheduler", help="Периодическое обновление")
    p_sched.add_argument("--interval", type=int, default=300)

    return parser


# --- форматирование ---

def _fmt_money(value: float) -> str:
    return f"{value:,.2f}"


def _fmt_amount(value: float) -> str:
    return f"{value:.4f}"


def _fmt_rate(value: float) -> str:
    if abs(value) >= 1:
        return f"{value:,.2f}"
    return f"{value:.8f}"


def _supported_codes() -> str:
    return ", ".join(c.code for c in list_currencies())


# --- обработчики ---

def _cmd_register(args) -> None:
    result = usecases.register(args.username, args.password)
    print(
        f"Пользователь '{result['username']}' зарегистрирован "
        f"(id={result['user_id']}). "
        f"Войдите: login --username {result['username']} --password ****"
    )


def _cmd_login(args) -> None:
    info = usecases.login(args.username, args.password)
    print(f"Вы вошли как '{info['username']}'")


def _cmd_logout(args) -> None:
    usecases.logout()
    print("Вы вышли из системы")


def _cmd_show_portfolio(args) -> None:
    data = usecases.show_portfolio(args.base)
    if not data["wallets"]:
        print(f"Портфель пользователя '{data['username']}' пуст.")
        return

    print(f"Портфель пользователя '{data['username']}' (база: {data['base']}):")
    table = PrettyTable()
    table.field_names = ["Валюта", "Баланс", f"Стоимость в {data['base']}"]
    table.align = "r"
    for row in data["wallets"]:
        table.add_row(
            [
                row["currency"],
                _fmt_amount(row["balance"]),
                _fmt_money(row["value_in_base"]),
            ]
        )
    print(table)
    print("-" * 33)
    print(f"ИТОГО: {_fmt_money(data['total'])} {data['base']}")


def _print_changes(r: dict, success_word: str) -> None:
    """Печатает блок 'Изменения в портфеле' для buy/sell."""
    print("Изменения в портфеле:")
    print(
        f"- {r['currency']}: было {_fmt_amount(r['before'])} "
        f"→ стало {_fmt_amount(r['after'])}"
    )
    if r["currency"] != "USD":
        print(
            f"- USD: было {_fmt_amount(r['usd_before'])} "
            f"→ стало {_fmt_amount(r['usd_after'])}"
        )


def _cmd_buy(args) -> None:
    r = usecases.buy(args.currency, args.amount)
    if r["rate"] is not None:
        print(
            f"Покупка выполнена: {_fmt_amount(r['amount'])} {r['currency']} "
            f"по курсу {_fmt_money(r['rate'])} USD/{r['currency']}"
        )
    else:
        print(f"Покупка выполнена: {_fmt_amount(r['amount'])} {r['currency']}")
    _print_changes(r, "Покупка")
    print(f"Оценочная стоимость покупки: {_fmt_money(r['estimated_usd'])} USD")


def _cmd_sell(args) -> None:
    r = usecases.sell(args.currency, args.amount)
    if r["rate"] is not None:
        print(
            f"Продажа выполнена: {_fmt_amount(r['amount'])} {r['currency']} "
            f"по курсу {_fmt_money(r['rate'])} USD/{r['currency']}"
        )
    else:
        print(f"Продажа выполнена: {_fmt_amount(r['amount'])} {r['currency']}")
    _print_changes(r, "Продажа")
    print(f"Оценочная выручка: {_fmt_money(r['estimated_usd'])} USD")


def _cmd_get_rate(args) -> None:
    forward = usecases.get_rate(args.from_currency, args.to_currency)
    src = args.from_currency.upper()
    dst = args.to_currency.upper()
    updated = forward.get("updated_at") or "-"
    suffix = " [устарел]" if forward.get("stale") else ""
    print(
        f"Курс {src}→{dst}: {_fmt_rate(forward['rate'])} "
        f"(обновлено: {updated}){suffix}"
    )
    try:
        back = usecases.get_rate(dst, src)
        back_suffix = " [устарел]" if back.get("stale") else ""
        print(f"Обратный курс {dst}→{src}: {_fmt_rate(back['rate'])}{back_suffix}")
    except (ApiRequestError, CurrencyNotFoundError):
        pass


def _cmd_list_currencies(args) -> None:
    table = PrettyTable()
    table.field_names = ["Код", "Инфо"]
    table.align = "l"
    for c in list_currencies():
        table.add_row([c.code, c.get_display_info()])
    print(table)

def _cmd_update_rates(args) -> None:
    from valutatrade_hub.parser_service.updater import run_update

    print("INFO: Starting rates update...")
    try:
        stats = run_update(source=args.source)
    except ValueError as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return

    for src in stats.get("sources", []):
        if "error" in src:
            print(f"ERROR: Failed to fetch from {src['name']}: {src['error']}")
        else:
            print(f"INFO: Fetching from {src['name']}... OK ({src['count']} rates)")

    if stats.get("pairs_updated", 0) == 0:
        print("Update failed: no rates fetched. Check logs for details.")
        return

    print(
        f"Update successful. Total rates updated: {stats['pairs_updated']}. "
        f"Last refresh: {stats['last_refresh']}"
    )
    if stats.get("errors", 0):
        print(f"Update completed with errors: {stats['errors']}. Check logs.")


def _cmd_show_rates(args) -> None:
    from valutatrade_hub.core.utils import load_rates

    data = load_rates()
    pairs = (
        data.get("pairs")
        if isinstance(data, dict) and "pairs" in data
        else data
    )
    if not isinstance(pairs, dict) or not pairs:
        print(
            "Локальный кеш курсов пуст. "
            "Выполните 'update-rates', чтобы загрузить данные."
        )
        return

    last_refresh = data.get("last_refresh") if isinstance(data, dict) else None
    print(f"Rates from cache (updated at {last_refresh or '-'}):")

    rows = []
    for pair, rec in pairs.items():
        if not isinstance(rec, dict):
            continue
        src_code, _, dst_code = pair.partition("_")
        rows.append(
            {
                "pair": pair,
                "from": src_code,
                "to": dst_code,
                "rate": float(rec.get("rate", 0.0)),
                "updated_at": rec.get("updated_at"),
                "source": rec.get("source"),
            }
        )

    if args.currency:
        cur = args.currency.upper()
        rows = [r for r in rows if r["from"] == cur or r["to"] == cur]
        if not rows:
            print(f"Курс для '{cur}' не найден в кеше.")
            return

    if args.base:
        base = args.base.upper()
        rows = [r for r in rows if r["to"] == base or r["from"] == base]
        if not rows:
            print(f"Курсы с базой '{base}' не найдены в кеше.")
            return

    if args.top:
        rows = sorted(rows, key=lambda r: r["rate"], reverse=True)[: args.top]
    else:
        rows = sorted(rows, key=lambda r: r["pair"])

    table = PrettyTable()
    table.field_names = ["Пара", "Курс", "Обновлено", "Источник"]
    table.align = "r"
    for r in rows:
        table.add_row(
            [
                r["pair"],
                f"{r['rate']:.8f}",
                r["updated_at"] or "-",
                r["source"] or "-",
            ]
        )
    print(table)


def _cmd_start_scheduler(args) -> None:
    from valutatrade_hub.parser_service.scheduler import Scheduler

    sched = Scheduler(interval_seconds=args.interval)
    print(
        f"Запуск планировщика с интервалом {args.interval} секунд. "
        "Ctrl+C — остановить."
    )
    try:
        sched.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        sched.stop()
        print("\nПланировщик остановлен.")

_HANDLERS = {
    "register": _cmd_register,
    "login": _cmd_login,
    "logout": _cmd_logout,
    "show-portfolio": _cmd_show_portfolio,
    "buy": _cmd_buy,
    "sell": _cmd_sell,
    "get-rate": _cmd_get_rate,
    "list-currencies": _cmd_list_currencies,
    "update-rates": _cmd_update_rates,
    "show-rates": _cmd_show_rates,
    "start-scheduler": _cmd_start_scheduler,
}


# --- разбор строки и выполнение ---

def _print_error(exc: Exception) -> None:
    """Печатает пользовательское сообщение для исключения."""
    if isinstance(exc, InsufficientFundsError):
        print(f"Ошибка: {exc}", file=sys.stderr)
    elif isinstance(exc, CurrencyNotFoundError):
        print(f"Ошибка: {exc}", file=sys.stderr)
        print(
            f"Поддерживаемые коды: {_supported_codes()}. "
            "См. help или команду list-currencies.",
            file=sys.stderr,
        )
    elif isinstance(exc, ApiRequestError):
        print(f"Ошибка: {exc}", file=sys.stderr)
        print(
            "Повторите попытку позже или проверьте подключение к сети.",
            file=sys.stderr,
        )
    elif isinstance(exc, ValutaTradeError):
        print(f"Ошибка: {exc}", file=sys.stderr)
    else:
        print(f"Ошибка: {exc}", file=sys.stderr)


def _dispatch(argv: list[str], parser: argparse.ArgumentParser) -> int:
    """Парсит argv, вызывает обработчик, ловит логические ошибки."""
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)

    handler = _HANDLERS.get(args.command)
    if handler is None:
        print(f"Неизвестная команда: {args.command}", file=sys.stderr)
        return 1
    try:
        handler(args)
    except (ValueError, TypeError) as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1
    except ValutaTradeError as e:
        _print_error(e)
        return 1
    return 0


# --- интерактивный режим ---

_HELP_TEXT = """Доступные команды:
  register --username <str> --password <str>   Регистрация
  login --username <str> --password <str>      Вход
  logout                                       Выход
  show-portfolio [--base <str>]                Портфель
  buy --currency <str> --amount <float>        Покупка
  sell --currency <str> --amount <float>       Продажа
  get-rate --from <str> --to <str>             Курс валюты
  list-currencies                              Список валют
  help                                         Справка
  update-rates [--source <str>]                Обновить курсы (coingecko|exchangerate)
  show-rates [--currency <str>] [--top <int>]  Курсы из кеша
  start-scheduler [--interval <int>]           Периодическое обновление
  exit | quit                                  Выход из программы"""


def repl(parser: argparse.ArgumentParser) -> int:
    """Интерактивный цикл: читает строки, выполняет команды."""
    print("valutatrade — интерактивный режим. Введите 'help' для справки.")
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line.startswith(">"):
            line = line[1:].strip()
        if not line:
            continue
        lowered = line.lower()
        if lowered in ("exit", "quit"):
            break
        if lowered == "help":
            print(_HELP_TEXT)
            continue

        argv = line.split()
        _dispatch(argv, parser)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Точка входа CLI. Без аргументов запускает REPL."""
    parser = _build_parser()
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        return repl(parser)
    return _dispatch(argv, parser)


if __name__ == "__main__":
    raise SystemExit(main())