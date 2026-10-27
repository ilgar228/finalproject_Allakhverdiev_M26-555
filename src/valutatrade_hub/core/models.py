"""Доменные модели платформы: пользователь, кошелёк, портфель."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime

from valutatrade_hub.core.currencies import Currency, get_currency
from valutatrade_hub.core.exceptions import (
    CurrencyNotFoundError,
    InsufficientFundsError,
)


class User:
    """Зарегистрированный пользователь платформы."""

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime,
    ) -> None:
        self._user_id = user_id
        self._username = username
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    # --- геттеры ---

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = value.strip()

    @property
    def hashed_password(self) -> str:
        return self._hashed_password

    @property
    def salt(self) -> str:
        return self._salt

    @property
    def registration_date(self) -> datetime:
        return self._registration_date

    # --- работа с паролем ---

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        """Считает sha256 от (пароль + соль) и возвращает hex-строку."""
        if not isinstance(password, str) or len(password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

    @classmethod
    def create(cls, user_id: int, username: str, password: str) -> "User":
        """Фабрика: создаёт пользователя со свежей солью и хешем пароля."""
        if not isinstance(username, str) or not username.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        salt = secrets.token_hex(8)
        hashed = cls._hash_password(password, salt)
        return cls(
            user_id=user_id,
            username=username.strip(),
            hashed_password=hashed,
            salt=salt,
            registration_date=datetime.now(),
        )

    def verify_password(self, password: str) -> bool:
        """Проверяет, совпадает ли пароль с сохранённым хешем.

        Возвращает False для заведомо невалидных паролей (не строка, короче 4),
        не поднимая исключение — это соответствует поведению «пароль не подходит».
        """
        if not isinstance(password, str) or len(password) < 4:
            return False
        return self._hash_password(password, self._salt) == self._hashed_password

    def change_password(self, new_password: str) -> None:
        """Меняет пароль, пересчитывая хеш с текущей солью."""
        self._hashed_password = self._hash_password(new_password, self._salt)

    # --- информация ---

    def get_user_info(self) -> dict:
        """Возвращает информацию о пользователе без пароля и соли."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
        }

    # --- (де)сериализация ---

    def to_dict(self) -> dict:
        """Преобразует пользователя в словарь для сохранения в JSON."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        """Восстанавливает пользователя из словаря (формат users.json)."""
        return cls(
            user_id=int(data["user_id"]),
            username=data["username"],
            hashed_password=data["hashed_password"],
            salt=data["salt"],
            registration_date=datetime.fromisoformat(data["registration_date"]),
        )


class Wallet:
    """Кошелёк пользователя для одной конкретной валюты."""

    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        if not isinstance(currency_code, str) or not currency_code.strip():
            raise ValueError("Код валюты не может быть пустым")
        self.currency_code = currency_code.strip().upper()
        self._balance = 0.0
        self.balance = balance  # присваивание идёт через сеттер с проверкой

    @property
    def currency(self) -> Currency:
        """Объект валюты из иерархии currencies (точка интеграции)."""
        return get_currency(self.currency_code)

    @property
    def balance(self) -> float:
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        # bool — подкласс int, поэтому исключаем его отдельно
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError("Баланс должен быть числом")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = float(value)

    @staticmethod
    def _validate_amount(amount: float) -> float:
        """Проверяет, что сумма — положительное число, и возвращает float."""
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            raise TypeError("Сумма должна быть числом")
        if amount <= 0:
            raise ValueError("Сумма должна быть положительным числом")
        return float(amount)

    def deposit(self, amount: float) -> None:
        """Пополняет баланс кошелька."""
        self._balance += self._validate_amount(amount)

    def withdraw(self, amount: float) -> None:
        """Снимает средства, если баланса достаточно.

        Кидает InsufficientFundsError, если средств не хватает.
        """
        amount = self._validate_amount(amount)
        if amount > self._balance:
            raise InsufficientFundsError(
                available=self._balance,
                required=amount,
                code=self.currency_code,
            )
        self._balance -= amount

    def get_balance_info(self) -> str:
        """Возвращает строку с информацией о балансе."""
        return f"{self.currency_code}: {self._balance:.4f}"

    # --- (де)сериализация ---

    def to_dict(self) -> dict:
        """Преобразует кошелёк в словарь для portfolios.json."""
        return {"currency_code": self.currency_code, "balance": self._balance}

    @classmethod
    def from_dict(cls, data: dict) -> "Wallet":
        """Восстанавливает кошелёк из словаря."""
        return cls(
            currency_code=data["currency_code"],
            balance=float(data["balance"]),
        )


class Portfolio:
    """Набор кошельков одного пользователя."""

    def __init__(
        self,
        user_id: int,
        wallets: dict[str, Wallet] | None = None,
        user: User | None = None,
    ) -> None:
        self._user_id = user_id
        self._user: User | None = user
        self._wallets: dict[str, Wallet] = {}
        if wallets:
            for code, wallet in wallets.items():
                self._wallets[code] = wallet

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def user(self) -> User | None:
        """Объект пользователя (только чтение). Может быть None, если не привязан."""
        return self._user

    def attach_user(self, user: User) -> None:
        """Привязывает объект пользователя к портфелю (для property user)."""
        if user.user_id != self._user_id:
            raise ValueError("user_id пользователя не совпадает с портфелем")
        self._user = user

    @property
    def wallets(self) -> dict[str, Wallet]:
        """Возвращает копию словаря кошельков (без возможности перезаписи)."""
        return dict(self._wallets)

    def add_currency(self, currency_code: str) -> Wallet:
        """Добавляет новый кошелёк, если такого ещё нет. Возвращает его.

        Валидирует код через иерархию валют (CurrencyNotFoundError для неизвестных).
        """
        if not isinstance(currency_code, str) or not currency_code.strip():
            raise ValueError("Код валюты не может быть пустым")
        code = currency_code.strip().upper()
        # проверка, что валюта известна (кидает CurrencyNotFoundError)
        get_currency(code)
        if code in self._wallets:
            raise ValueError(f"Кошелёк '{code}' уже существует в портфеле")
        wallet = Wallet(code)
        self._wallets[code] = wallet
        return wallet

    def get_wallet(self, currency_code: str) -> Wallet | None:
        """Возвращает кошелёк по коду валюты или None, если его нет."""
        if not isinstance(currency_code, str):
            return None
        return self._wallets.get(currency_code.strip().upper())

    def get_total_value(
        self,
        base_currency: str = "USD",
        rate_provider=None,
    ) -> float:
        """Считает общую стоимость всех кошельков в базовой валюте.

        Если передан rate_provider(code, base) -> float, используется он.
        Иначе — фиксированные курсы-заглушки из EXCHANGE_RATES.
        """
        base = base_currency.strip().upper() if isinstance(base_currency, str) else ""
        try:
            get_currency(base)
        except CurrencyNotFoundError:
            raise CurrencyNotFoundError(base) from None

        total = 0.0
        for code, wallet in self._wallets.items():
            if code == base:
                total += wallet.balance
                continue
            if rate_provider is not None:
                rate = rate_provider(code, base)
            else:
                rate = self._fallback_rate(code, base)
            total += wallet.balance * rate
        return total

    @staticmethod
    def _fallback_rate(code: str, base: str) -> float:
        """Фиксированные курсы-заглушки, если rate_provider не передан."""
        rates = {
            "USD": 1.0,
            "EUR": 1.0786,
            "RUB": 0.01016,
            "BTC": 59337.21,
            "ETH": 3720.00,
        }
        if code not in rates:
            raise CurrencyNotFoundError(code)
        if base not in rates:
            raise CurrencyNotFoundError(base)
        return rates[code] / rates[base]

    # --- (де)сериализация ---

    def to_dict(self) -> dict:
        """Преобразует портфель в словарь для portfolios.json."""
        return {
            "user_id": self._user_id,
            "wallets": {code: w.to_dict() for code, w in self._wallets.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Portfolio":
        """Восстанавливает портфель из словаря."""
        wallets = {
            code: Wallet.from_dict(w) for code, w in data.get("wallets", {}).items()
        }
        return cls(user_id=int(data["user_id"]), wallets=wallets)