import abc
import aiohttp
from moneyed import Money
from typing import Optional


class SecurityService(abc.ABC):
    async def get_security_price(self, name: str) -> Optional[Money]: ...

    async def get_security_prices(
        self, names: list[str]
    ) -> Optional[dict[str, Money]]: ...


class SecurityServiceImpl(SecurityService):
    finnhub_api_key: str

    def __init__(self, finnhub_api_key: str) -> None:
        self.finnhub_api_key = finnhub_api_key

    async def get_security_price(self, name: str) -> Optional[Money]:
        async with aiohttp.ClientSession() as session:
            return await get_security_price(session, self.finnhub_api_key, name)

    async def get_security_prices(self, names: list[str]) -> Optional[dict[str, Money]]:
        prices: dict[str, Money] = {}
        async with aiohttp.ClientSession() as session:
            for name in names:
                price = await get_security_price(session, self.finnhub_api_key, name)
                if price is None:
                    return None
                prices[name] = price
        return prices


async def get_security_price(
    session: aiohttp.ClientSession, token: str, symbol: str
) -> Optional[Money]:
    async with session.get(
        f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={token}"
    ) as resp:
        if resp.status == 404:
            return None
        elif resp.status != 200:
            text = resp.text()
            raise Exception(
                f"API call to finnhub failed with status {resp.status} and response: {text}"
            )
        response = await resp.json()
        price = response["c"]
        return Money(price, "USD")
