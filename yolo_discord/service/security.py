import abc
from moneyed import Money


class SecurityService(abc.ABC):
    async def get_security_price(self, name: str) -> Money: ...

    async def get_security_prices(self, names: list[str]) -> dict[str, Money]: ...


class SecurityServiceImpl(SecurityService):
    async def get_security_price(self, name: str) -> Money:
        return Money(0, "USD")

    async def get_security_prices(self, names: list[str]) -> dict[str, Money]:
        return {name: Money(0, "USD") for name in names}
