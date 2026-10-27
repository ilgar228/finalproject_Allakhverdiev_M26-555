from valutatrade_hub.decorators import log_action
from valutatrade_hub.logging_config import get_logger


@log_action("REGISTER")
def fake_register(username, password):
    return {"username": username}


@log_action("BUY", verbose=True)
def fake_buy(currency, amount):
    return {"currency": currency, "amount": amount, "before": 0.0, "after": amount}


@log_action("SELL")
def fake_sell(currency, amount):
    raise ValueError("недостаточно средств")


print(fake_register(username="alice", password="1234"))
print(fake_buy(currency="BTC", amount=0.05))
try:
    fake_sell(currency="BTC", amount=10)
except ValueError as e:
    print("caught:", e)

logger = get_logger()
print("log file:", logger.handlers[0].baseFilename)