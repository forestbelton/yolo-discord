import abc
import aiohttp
from cachebox import TTLCache
from moneyed import Money
from typing import Optional


class SecurityService(abc.ABC):
    async def get_security_price(self, name: str) -> Optional[Money]: ...

    async def get_security_prices(
        self, names: list[str]
    ) -> Optional[dict[str, Money]]: ...


class SecurityServiceImpl(SecurityService):
    finnhub_api_key: str
    price_cache: TTLCache[str, Money]

    def __init__(self, finnhub_api_key: str) -> None:
        self.finnhub_api_key = finnhub_api_key
        self.price_cache = TTLCache(0, ttl=900)

    async def get_security_price(self, name: str) -> Optional[Money]:
        async with aiohttp.ClientSession() as session:
            return await self.fetch_price_through_cache(session, name)

    async def get_security_prices(self, names: list[str]) -> Optional[dict[str, Money]]:
        prices: dict[str, Money] = {}
        async with aiohttp.ClientSession() as session:
            for name in names:
                price = await self.fetch_price_through_cache(session, name)
                if price is None:
                    return None
                prices[name] = price
        return prices

    async def fetch_price_through_cache(
        self, session: aiohttp.ClientSession, name: str
    ) -> Optional[Money]:
        try:
            price = self.price_cache[name]
        except KeyError:
            price = await fetch_security_price(session, self.finnhub_api_key, name)
        if price is not None:
            self.price_cache[name] = price
        return price


async def fetch_security_price(
    session: aiohttp.ClientSession, token: str, symbol: str
) -> Optional[Money]:
    async with session.get(
        f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={token}"
    ) as resp:
        if resp.status == 404:
            return None
        elif resp.status != 200:
            text = await resp.text()
            raise Exception(
                f"API call to finnhub failed with status {resp.status} and response: {text}"
            )
        response = await resp.json()
        price = response["c"]
        return Money(price, "USD")
