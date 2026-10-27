"""Бизнес-логика платформы: регистрация, логин, портфель, покупка/продажа, курсы."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from valutatrade_hub.core import utils
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    InsufficientFundsError,
)
from valutatrade_hub.core.models import Portfolio, User
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import get_database
from valutatrade_hub.infra.settings import get_settings

# Текущий залогиненный пользователь (сессия в рамках процесса CLI)
_current_user: User | None = None


# --- сессия ---

def get_current_user() -> User | None:
    """Возвращает текущего залогиненного пользователя или None."""
    return _current_user


def _require_login() -> User:
    """Проверяет, что пользователь залогинен; иначе кидает ValueError."""
    if _current_user is None:
        raise ValueError("Сначала выполните login")
    return _current_user


def logout() -> None:
    """Завершает сессию."""
    global _current_user
    _current_user = None


# --- вспомогательное ---

def _next_user_id(users: list[dict]) -> int:
    if not users:
        return 1
    return max(int(u["user_id"]) for u in users) + 1


def _find_user_record(users: list[dict], username: str) -> dict | None:
    for u in users:
        if u["username"] == username:
            return u
    return None


def _load_portfolio_for(user_id: int) -> Portfolio:
    """Загружает портфель пользователя из portfolios.json (или пустой)."""
    db = get_database()
    records = db.load(db.portfolios_file, [])
    for rec in records:
        if int(rec["user_id"]) == user_id:
            return Portfolio.from_dict(rec)
    return Portfolio(user_id=user_id)


def _save_portfolio(portfolio: Portfolio) -> None:
    """Сохраняет портфель, заменяя запись с тем же user_id."""
    db = get_database()
    new_rec = portfolio.to_dict()

    def mutator(records: list[dict]) -> list[dict]:
        records = records or []
        for i, rec in enumerate(records):
            if int(rec["user_id"]) == portfolio.user_id:
                records[i] = new_rec
                return records
        records.append(new_rec)
        return records

    db.update(db.portfolios_file, mutator, default=[])


def _validate_amount(amount: float) -> float:
    if not isinstance(amount, (int, float)) or isinstance(amount, bool):
        raise TypeError("'amount' должен быть числом")
    if amount <= 0:
        raise ValueError("'amount' должен быть положительным числом")
    return float(amount)


def _ensure_wallet(portfolio: Portfolio, code: str):
    """Возвращает кошелёк, создавая его при необходимости."""
    wallet = portfolio.get_wallet(code)
    if wallet is None:
        wallet = portfolio.add_currency(code)
    return wallet


def _rates_ttl() -> timedelta:
    settings = get_settings()
    return timedelta(seconds=settings.rates_ttl_seconds)


def _strict_ttl() -> bool:
    settings = get_settings()
    return bool(settings.get("rates_strict_ttl", False))


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


# --- регистрация и логин ---

@log_action("REGISTER")
def register(username: str, password: str) -> dict:
    """Создаёт нового пользователя и пустой портфель."""
    db = get_database()
    users = db.load(db.users_file, [])
    if not isinstance(username, str) or not username.strip():
        raise ValueError("Имя пользователя не может быть пустым")
    username = username.strip()
    if _find_user_record(users, username) is not None:
        raise ValueError(f"Имя пользователя '{username}' уже занято")

    user_id = _next_user_id(users)
    user = User.create(user_id=user_id, username=username, password=password)
    users.append(user.to_dict())
    db.save(db.users_file, users)

    _save_portfolio(Portfolio(user_id=user_id))
    return {"user_id": user_id, "username": username}


@log_action("LOGIN")
def login(username: str, password: str) -> dict:
    """Логинит пользователя, сохраняя его в сессии."""
    global _current_user
    db = get_database()
    users = db.load(db.users_file, [])
    name = username.strip() if isinstance(username, str) else ""
    record = _find_user_record(users, name)
    if record is None:
        raise ValueError(f"Пользователь '{username}' не найден")
    user = User.from_dict(record)
    if not user.verify_password(password):
        raise ValueError("Неверный пароль")
    _current_user = user
    return user.get_user_info()


# --- портфель ---

def show_portfolio(base: str = "USD") -> dict:
    """Возвращает данные о портфеле: список кошельков и итог в base."""
    user = _require_login()
    portfolio = _load_portfolio_for(user.user_id)
    portfolio.attach_user(user)
    base_code = utils.validate_currency_code(base)

    rows = []
    for code, wallet in portfolio.wallets.items():
        if code == base_code:
            value = wallet.balance
        else:
            rate = get_rate(code, base_code)["rate"]
            value = wallet.balance * rate
        rows.append(
            {
                "currency": code,
                "balance": wallet.balance,
                "value_in_base": value,
            }
        )

    total = portfolio.get_total_value(
        base_code,
        rate_provider=lambda c, b: get_rate(c, b)["rate"],
    )
    return {
        "username": user.username,
        "base": base_code,
        "wallets": rows,
        "total": total,
    }


# --- покупка/продажа (через USD-кошелёк) ---

def _estimate_usd_amount(currency: str, amount: float) -> tuple[float, dict | None]:
    if currency == "USD":
        return amount, None
    rate_info = get_rate(currency, "USD")
    return amount * rate_info["rate"], rate_info


@log_action("BUY", verbose=True)
def buy(currency: str, amount: float) -> dict:
    """Покупает валюту: списывает USD и увеличивает баланс кошелька."""
    user = _require_login()
    code = utils.validate_currency_code(currency)
    amount = _validate_amount(amount)

    portfolio = _load_portfolio_for(user.user_id)
    usd_cost, rate_info = _estimate_usd_amount(code, amount)

    if code != "USD":
        usd_wallet = _ensure_wallet(portfolio, "USD")
        usd_before = usd_wallet.balance
        try:
            usd_wallet.withdraw(usd_cost)
        except InsufficientFundsError as e:
            raise InsufficientFundsError(
                available=e.available, required=e.required, code="USD"
            ) from None
    else:
        usd_wallet = _ensure_wallet(portfolio, "USD")
        usd_before = usd_wallet.balance
        usd_wallet.deposit(amount)

    target_wallet = _ensure_wallet(portfolio, code)
    before = target_wallet.balance
    if code != "USD":
        target_wallet.deposit(amount)
    _save_portfolio(portfolio)

    return {
        "currency": code,
        "amount": amount,
        "before": before,
        "after": target_wallet.balance,
        "rate": rate_info["rate"] if rate_info else None,
        "estimated_usd": usd_cost,
        "usd_before": usd_before,
        "usd_after": portfolio.get_wallet("USD").balance
        if portfolio.get_wallet("USD")
        else 0.0,
        "user": user.username,
    }


@log_action("SELL", verbose=True)
def sell(currency: str, amount: float) -> dict:
    """Продаёт валюту: уменьшает баланс кошелька и начисляет USD."""
    user = _require_login()
    code = utils.validate_currency_code(currency)
    amount = _validate_amount(amount)

    portfolio = _load_portfolio_for(user.user_id)
    wallet = portfolio.get_wallet(code)
    if wallet is None:
        raise ValueError(
            f"У вас нет кошелька '{code}'. "
            "Добавьте валюту: она создаётся автоматически при первой покупке."
        )

    proceeds_usd, rate_info = _estimate_usd_amount(code, amount)
    before = wallet.balance
    wallet.withdraw(amount)  # кидает InsufficientFundsError при нехватке

    usd_before = 0.0
    if code != "USD":
        usd_wallet = _ensure_wallet(portfolio, "USD")
        usd_before = usd_wallet.balance
        usd_wallet.deposit(proceeds_usd)

    _save_portfolio(portfolio)

    return {
        "currency": code,
        "amount": amount,
        "before": before,
        "after": wallet.balance,
        "rate": rate_info["rate"] if rate_info else None,
        "estimated_usd": proceeds_usd,
        "usd_before": usd_before,
        "usd_after": portfolio.get_wallet("USD").balance
        if portfolio.get_wallet("USD")
        else 0.0,
        "user": user.username,
    }


# --- курсы ---

def _get_rate_from_cache(
    src: str, dst: str
) -> tuple[float, str | None, dict[str, Any]]:
    """Ищет курс в rates.json (прямой или обратный).

    Возвращает (rate, updated_at, rates).
    """
    rates = utils.load_rates()
    direct_key = f"{src}_{dst}"
    inverse_key = f"{dst}_{src}"

    if direct_key in rates and isinstance(rates[direct_key], dict):
        rec = rates[direct_key]
        return float(rec["rate"]), rec.get("updated_at"), rates
    if inverse_key in rates and isinstance(rates[inverse_key], dict):
        rec = rates[inverse_key]
        inverse = float(rec["rate"])
        rate = 1.0 / inverse if inverse else 0.0
        return rate, rec.get("updated_at"), rates

    raise ApiRequestError(f"нет данных для {src}→{dst}")


@log_action("GET_RATE")
def get_rate(from_currency: str, to_currency: str) -> dict:
    """Возвращает курс from→to из кеша rates.json и признак свежести.

    Если кеш устарел:
      - при rates_strict_ttl = true  → ApiRequestError;
      - иначе                        → возвращаем с stale=True.
    """
    src = utils.validate_currency_code(from_currency)
    dst = utils.validate_currency_code(to_currency)

    if src == dst:
        return {
            "rate": 1.0,
            "updated_at": None,
            "source": "identity",
            "fresh": True,
            "stale": False,
        }

    try:
        rate, updated_at, rates = _get_rate_from_cache(src, dst)
    except ApiRequestError:
        # нет курса — это уже ApiRequestError
        raise

    updated_dt = _parse_iso(updated_at)
    fresh = True
    if updated_dt is not None:
        fresh = (datetime.now() - updated_dt) <= _rates_ttl()

    if not fresh and _strict_ttl():
        # В строгом режиме пытаемся «обновить» — заглушка Parser Service недоступна
        raise ApiRequestError(
            f"кеш курса {src}→{dst} устарел, Parser Service недоступен"
        )

    return {
        "rate": rate,
        "updated_at": updated_at,
        "source": rates.get("source", "cache"),
        "fresh": fresh,
        "stale": not fresh,
    }


def now_iso() -> str:
    """Текущее время в ISO-формате (для CLI/логов)."""
    return datetime.now().isoformat(timespec="seconds")