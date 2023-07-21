import asyncio
import platform
import sys
from typing import List, Coroutine, AsyncIterator, Tuple
from datetime import date, timedelta

import aiohttp


privat_url = 'https://api.privatbank.ua/p24api/exchange_rates?json&date='

user_args = sys.argv[1:]

CUR_LIST: List[str] = ['EUR', 'USD']


def create_dates_list(days: int) -> List[str] | None:
    current_date = date.today()
    if days <= 10:
        return [(current_date - timedelta(days=i)).strftime('%d.%m.%Y') for i in range(days)]
    print('You can not take info about currency for more than 10 days!')
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


def get_currency(source: dict, cur: str) -> dict:
    for el in source['exchangeRate']:
        if el['currency'] == cur:
            return {cur: dict(sale=el['saleRate'],
                              purchase=el['purchaseRate'])}
    print(f'There is not a such currency: {cur} in a database!')


def create_curr_dict(curr_list: list, source: dict) -> dict:
    curr_dict: dict = {}
    for cur in curr_list:
        currency = get_currency(source, cur)
        if currency:
            curr_dict.update(currency)
    return curr_dict


def create_answer_sync(full_response: list, curr_list: list):
    total: list = []
    for record in full_response:
        total.append({record['date']: create_curr_dict(curr_list, record)})
    return total


def parse_arguments(arguments: list) -> Tuple[int, str] | int | str:
    if len(arguments) == 2:
        try:
            return int(arguments[0]), arguments[1]
        except ValueError:
            print('First argument should be a number and second - currency')
            return 1, arguments[1]
    elif len(arguments) == 1:
        try:
            return int(*arguments)
        except ValueError:
            return arguments[0]
    elif len(arguments) == 0:
        return 1
    else:
        return parse_arguments(arguments[:2])


def handle_response(args: Tuple[int, str] | int | str) -> List:
    answer_: list = []
    if isinstance(args, tuple):
        answer_ = process(args[0], args[1])
    elif isinstance(args, int):
        answer_ = process(args)
    elif isinstance(args, str):
        answer_ = process(1, args)
    if answer_:
        return answer_


async def async_main(days: int) -> List:
    dates_list: list = create_dates_list(days)
    if dates_list:
        iter_response = create_response(dates_list)
        return await get_response(iter_response)


def process(days: int, curr: str = None) -> list:
    if curr:
        if curr not in CUR_LIST:
            CUR_LIST.append(curr)
        else:
            CUR_LIST.clear()
            CUR_LIST.append(curr)
    result_list_ = asyncio.run(async_main(days))
    if result_list_:
        return create_answer_sync(result_list_, CUR_LIST)


if __name__ == '__main__':
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    res_args = parse_arguments(user_args)
    result = handle_response(res_args)
    if result:
        for records in result:
            print(records)
