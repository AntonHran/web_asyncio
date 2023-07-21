import asyncio
import platform
import sys
from typing import List, Coroutine, AsyncIterator, Tuple
from datetime import date, timedelta

import aiohttp


privat_url = 'https://api.privatbank.ua/p24api/exchange_rates?json&date='

user_args = sys.argv[1:]

CUR_LIST: Tuple[str, str] = ('EUR', 'USD')


def parse_dates(dates_list: List[str]) -> int:
    if dates_list:
        try:
            return int(dates_list[0])
        except (TypeError, ValueError) as error:
            print(f'Error: {error}\nYou should write days number, nothing else!')
    return 1


def create_dates_list(days: int) -> List[str] | None:
    current_date = date.today()
    if days <= 10:
        return [(current_date - timedelta(days=i)).strftime('%d.%m.%Y') for i in range(days)]
    print('You can not take info about currency for more then 10 days!')
    return None


async def get_request(url: str) -> dict | None:
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                print(f'Error status: {response.status} for {url}')
                return None
        except aiohttp.ClientConnectionError as error:
            print(f'Connection error: {error} for {url}')
        return None


async def create_response(dates: List[str]) -> AsyncIterator:
    for date_cur in dates:
        if await get_request(privat_url+date_cur):
            yield get_request(privat_url+date_cur)


async def get_response(response: AsyncIterator) -> List[Coroutine]:
    response_ = [res async for res in response if res]
    if response_:
        return await asyncio.gather(*response_)


def answer_sync(res: list):
    res_list = [create_response_sync(el) for el in res]
    [print(currency) for currency in res_list]


def create_response_sync(res: dict) -> dict:
    return {res['date']: {cur: get_currency(res, cur) for cur in CUR_LIST}}


def get_currency(source: dict, cur: str) -> dict:
    for el in source['exchangeRate']:
        if el['currency'] == cur:
            return dict(sale=el['saleRate'],
                        purchase=el['purchaseRate'])


async def async_main() -> List:
    dates_str: List[str] = create_dates_list(parse_dates(user_args))
    if dates_str:
        iter_response = create_response(dates_str)
        return await get_response(iter_response)


if __name__ == '__main__':
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    result_list = asyncio.run(async_main())
    if result_list:
        answer_sync(result_list)
