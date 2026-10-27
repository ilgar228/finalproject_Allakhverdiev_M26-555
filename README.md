# ValutaTrade Hub — платформа для симуляции торговли валютами

Учебный проект: консольное приложение (CLI), которое имитирует виртуальный
портфель фиатных и крипто-валют. Пользователь может зарегистрироваться,
войти, покупать и продавать валюту, смотреть портфель и актуальные курсы.
Курсы подтягиваются из внешних API (CoinGecko и ExchangeRate-API) отдельным
сервисом — Parser Service.

## Возможности

- Регистрация и вход (пароль хранится как `sha256(password + salt)`).
- Портфель с кошельками по каждой валюте (`USD`, `EUR`, `GBP`, `RUB`,
  `BTC`, `ETH`, `SOL`).
- Покупка и продажа валюты с расчётом через USD-кошелёк.
- Просмотр портфеля с итоговой стоимостью в выбранной базовой валюте.
- Получение курса валюты из локального кеша с учётом TTL.
- Parser Service: обновление курсов из CoinGecko (крипто) и
  ExchangeRate-API (фиат), история измерений в `exchange_rates.json`.
- Логирование действий (`@log_action`), доменные исключения,
  Singleton-конфигурация и Singleton-хранилище.

## Технологии

- Python 3.12
- [uv](https://docs.astral.sh/uv/) — управление зависимостями и сборка пакета
- `prettytable` — таблицы в CLI
- `requests` — HTTP-запросы к API
- `ruff` — линтер (dev-зависимость)

## Установка

```bash
git clone https://github.com/ilgar228/finalproject_Allahverdiyev_M26-555.git
cd finalproject_Allahverdiyev_M26-555
uv sync
```

### Ключ ExchangeRate-API

Ключ нужен только для обновления фиатных курсов. Он **не хранится в коде**.
Два способа задать ключ:

1. Переменная окружения (рекомендуется):

   ```powershell
   $env:EXCHANGERATE_API_KEY = "ваш_ключ"
   ```

   ```bash
   export EXCHANGERATE_API_KEY="ваш_ключ"
   ```

2. Локальный файл `src/valutatrade_hub/parser_service/config_local.py`
   (в `.gitignore`, в репозиторий не попадёт):

   ```python
   EXCHANGERATE_API_KEY = "ваш_ключ"
   ```

CoinGecko работает без ключа (публичный доступ).

## Запуск

Интерактивный режим:

```bash
uv run valutatrade
```

Или отдельные команды:

```bash
uv run valutatrade register --username alice --password 1234
uv run valutatrade login --username alice --password 1234
uv run valutatrade show-portfolio
uv run valutatrade buy --currency BTC --amount 0.05
uv run valutatrade sell --currency BTC --amount 0.01
uv run valutatrade get-rate --from USD --to BTC
```

## Команды CLI

| Команда | Аргументы | Описание |
|---|---|---|
| `register` | `--username`, `--password` | Регистрация пользователя |
| `login` | `--username`, `--password` | Вход в систему |
| `logout` | — | Выход |
| `show-portfolio` | `--base` (по умолчанию `USD`) | Портфель и итоговая стоимость |
| `buy` | `--currency`, `--amount` | Купить валюту (списывает USD) |
| `sell` | `--currency`, `--amount` | Продать валюту (начисляет USD) |
| `get-rate` | `--from`, `--to` | Курс валюты из кеша |
| `list-currencies` | — | Поддерживаемые валюты |
| `update-rates` | `--source` (`coingecko` / `exchangerate`) | Обновить курсы из API |
| `show-rates` | `--currency`, `--top`, `--base` | Курсы из кеша с фильтрами |
| `start-scheduler` | `--interval` (секунды, по умолчанию 300) | Периодическое обновление |
| `help` | — | Справка (в интерактивном режиме) |
| `exit` / `quit` | — | Выход из интерактивного режима |

## Пример сессии

```
> register --username alice --password 1234
Пользователь 'alice' зарегистрирован (id=1). Войдите: login --username alice --password ****
> login --username alice --password 1234
Вы вошли как 'alice'
> buy --currency USD --amount 5000
Покупка выполнена: 5000.0000 USD
Изменения в портфеле:
- USD: было 0.0000 → стало 5000.0000
Оценочная стоимость покупки: 5,000.00 USD
> buy --currency BTC --amount 0.05
Покупка выполнена: 0.0500 BTC по курсу 80,099.00 USD/BTC
Изменения в портфеле:
- BTC: было 0.0000 → стало 0.0500
- USD: было 5000.0000 → стало 995.0500
Оценочная стоимость покупки: 4,004.95 USD
> show-portfolio
Портфель пользователя 'alice' (база: USD):
+--------+-----------+-----------------+
| Валюта |    Баланс | Стоимость в USD |
+--------+-----------+-----------------+
|    USD |  995.0500 |          995.05 |
|    BTC |    0.0500 |        4,004.95 |
+--------+-----------+-----------------+
---------------------------------
ИТОГО: 5,000.00 USD
> get-rate --from BTC --to USD
Курс BTC→USD: 80,099.00 (обновлено: 2026-10-27T12:33:20Z)
Обратный курс USD→BTC: 0.00001248
> exit
```

## Parser Service и кэш курсов

Parser Service — отдельный модуль `valutatrade_hub/parser_service/`,
который по запросу или по расписанию обновляет курсы.

- `update-rates` — разовое обновление из обоих источников (или одного
  через `--source`).
- `show-rates` — просмотр кеша с фильтрами (`--currency`, `--top`, `--base`).
- `start-scheduler --interval N` — периодическое обновление раз в N секунд
  (первое — сразу, `Ctrl+C` останавливает).

Хранилище:

- `data/rates.json` — «снимок» актуальных курсов:

  ```json
  {
    "pairs": {
      "BTC_USD": {"rate": 80099.0, "updated_at": "2026-10-27T12:33:20Z", "source": "CoinGecko"},
      "EUR_USD": {"rate": 1.1186, "updated_at": "2026-10-27T12:33:20Z", "source": "ExchangeRate-API"}
    },
    "last_refresh": "2026-10-27T12:33:20Z"
  }
  ```

- `data/exchange_rates.json` — история измерений, каждая запись с
  `id = <FROM>_<TO>_<timestamp>`.

TTL кэша задаётся в `pyproject.toml` в секции `[tool.valutatrade]`:

```toml
[tool.valutatrade]
rates_ttl_seconds = 300     # 5 минут
rates_strict_ttl = false    # false: устаревший курс возвращается с флагом stale
                            # true:  устаревший курс → ApiRequestError
```

Если `rates_strict_ttl = false`, `get-rate` вернёт курс с пометкой
`[устарел]`, но не упадёт. Если `true` — попытается «обновить» через
Parser Service и кинет `ApiRequestError`, если обновление недоступно.

## Структура проекта

```
final_project/
├── data/                              # JSON-хранилище (в .gitignore)
│   ├── users.json
│   ├── portfolios.json
│   ├── rates.json                     # кэш для Core Service
│   └── exchange_rates.json            # история Parser Service
├── src/valutatrade_hub/
│   ├── __init__.py
│   ├── logging_config.py              # настройка логов (формат, ротация)
│   ├── decorators.py                  # @log_action
│   ├── core/
│   │   ├── currencies.py              # Currency / Fiat / Crypto, get_currency
│   │   ├── exceptions.py              # InsufficientFundsError, CurrencyNotFoundError, ApiRequestError
│   │   ├── models.py                  # User, Wallet, Portfolio
│   │   ├── usecases.py                # register/login/buy/sell/get_rate
│   │   └── utils.py                   # валидации, конвертация, JSON-обёртки
│   ├── infra/
│   │   ├── settings.py                # Singleton SettingsLoader
│   │   └── database.py                # Singleton DatabaseManager
│   ├── parser_service/
│   │   ├── config.py                  # ParserConfig
│   │   ├── api_clients.py             # BaseApiClient, CoinGeckoClient, ExchangeRateApiClient
│   │   ├── storage.py                 # rates.json + exchange_rates.json
│   │   ├── updater.py                 # RatesUpdater.run_update
│   │   └── scheduler.py               # Scheduler
│   └── cli/
│       └── interface.py               # команды и REPL
├── main.py
├── pyproject.toml
├── uv.lock
├── README.md
└── .gitignore
```

> В проекте используется `src/`-layout — стандартная практика для
> uv-пакетов. Импорт остаётся `from valutatrade_hub...`.

## Логирование

- Файл: `logs/actions.log` (путь задаётся в `[tool.valutatrade]`).
- Формат: текстовый (по умолчанию) или JSON (`log_format = "json"`).
- Ротация: по размеру (`log_max_bytes`, `log_backup_count`).
- Уровень: `INFO` по умолчанию, `DEBUG` для отладки.
- `@log_action` применён к `register`, `login`, `buy`, `sell`, `get_rate`.
  Для `buy`/`sell` включён `verbose=True` — в лог попадает состояние
  «было → стало».

Пример записи:

```
INFO 2026-10-27T12:33:20 BUY user='alice' currency='BTC' amount=0.0500 result=OK
```

## Доменные исключения

- `InsufficientFundsError` — не хватает средств на кошельке.
- `CurrencyNotFoundError` — неизвестный код валюты.
- `ApiRequestError` — сбой внешнего API (сеть, HTTP, ключ, лимит).

CLI перехватывает их и печатает понятные сообщения, не смешивая с
обычными `ValueError`/`TypeError`.

## Разработка

```bash
uv run ruff check .
uv run ruff check . --fix
uv build
uvx twine check dist/*
```

