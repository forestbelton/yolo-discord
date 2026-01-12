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
    alphavantage_api_key: str

    def __init__(self, alphavantage_api_key: str) -> None:
        self.alphavantage_api_key = alphavantage_api_key

    async def get_security_price(self, name: str) -> Optional[Money]:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={name}&apikey={self.alphavantage_api_key}') as resp:
                if resp.status != 200:
                    raise Exception(f'API call to alphavantage failed with status {resp.status} and response: {text}')

                response = await resp.json()
                price = response['Global Quote']['05. price']

                return Money(price, "USD")

    async def get_security_prices(self, names: list[str]) -> Optional[dict[str, Money]]:
        return {name: Money(0, "USD") for name in names}
