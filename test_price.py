import asyncio
import aiohttp
from moneyed import Money

async def get_latest_price(ticker: str) -> str:
    api_key = 'TVAVG6RZPRKLE2DG'

    async with aiohttp.ClientSession() as session:
        async with session.get(f'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={api_key}') as resp:
            if resp.status != 200:
                raise Exception(f'API call to alphavantage failed with status {resp.status} and response: {text}')

            response = await resp.json()

            return response['Global Quote']['05. price']


async def main():
    price = await get_latest_price('GOOGL')
    print(price)


if __name__ == '__main__':
    asyncio.run(main())
