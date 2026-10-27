"""Временный скрипт проверки этапа 3 (модели, utils, usecases, логирование)."""

from valutatrade_hub.core import usecases, utils
from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from valutatrade_hub.core.models import Portfolio, User, Wallet

print("=== models ===")
u = User.create(user_id=1, username="alice", password="1234")
print("user:", u.get_user_info())
print("verify:", u.verify_password("1234"), u.verify_password("bad"))

w = Wallet("btc")
w.deposit(0.05)
print("wallet currency:", w.currency.get_display_info())
try:
    w.withdraw(1)
except InsufficientFundsError as e:
    print("insufficient ->", e)

p = Portfolio(user_id=1)
p.add_currency("usd").deposit(1000)
try:
    p.add_currency("XYZ")
except CurrencyNotFoundError as e:
    print("unknown currency ->", e)
p.add_currency("btc").deposit(0.01)
print("total (fallback):", round(p.get_total_value("USD"), 2))

print("\n=== utils ===")
print("validate usd:", utils.validate_currency_code("usd"))
try:
    utils.validate_currency_code("XYZ")
except CurrencyNotFoundError as e:
    print("unknown ->", e)

def provider(src, dst):
    rates = {"USD": 1.0, "EUR": 1.0786, "BTC": 59337.21}
    return rates[src] / rates[dst]

print("convert 1 EUR -> USD:", round(utils.convert(1, "EUR", "USD", provider), 4))
print("convert 0.01 BTC -> USD:", round(utils.convert(0.01, "BTC", "USD", provider), 2))

print("\n=== usecases (полный сценарий) ===")
utils.save_users([])
utils.save_portfolios([])
usecases.logout()

print("register:", usecases.register("alice", "1234"))
print("login:", usecases.login("alice", "1234"))
print("portfolio empty:", usecases.show_portfolio())

print("buy USD:", usecases.buy("usd", 5000))
print("buy BTC:", usecases.buy("btc", 0.05))
print("portfolio:", usecases.show_portfolio())

print("sell BTC:", usecases.sell("BTC", 0.01))
print("rate BTC->USD:", usecases.get_rate("BTC", "USD"))
print("rate USD->BTC:", usecases.get_rate("usd", "btc"))

usecases.logout()
try:
    usecases.buy("BTC", 0.01)
except ValueError as e:
    print("not logged ->", e)

try:
    usecases.register("alice", "1234")
except ValueError as e:
    print("dup username ->", e)

# логин, чтобы проверить sell
usecases.login("alice", "1234")
try:
    usecases.sell("ETH", 1)
except ValueError as e:
    print("no wallet ->", e)

try:
    usecases.sell("BTC", 100)
except InsufficientFundsError as e:
    print("insufficient sell ->", e)

try:
    usecases.buy("XYZ", 1)
except CurrencyNotFoundError as e:
    print("unknown currency buy ->", e)

# проверка строгого режима TTL (по умолчанию false — не должно упасть)
try:
    r = usecases.get_rate("BTC", "USD")
    print("rate stale?:", r["stale"], "fresh?:", r["fresh"])
except ApiRequestError as e:
    print("api error ->", e)

print("\n=== log file ===")
print("см. logs/actions.log")