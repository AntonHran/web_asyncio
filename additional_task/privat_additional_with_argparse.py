import argparse
import asyncio
import platform
from typing import List, Coroutine, AsyncIterator
from datetime import date, timedelta

import aiohttp


privat_url = 'https://api.privatbank.ua/p24api/exchange_rates?json&date='

CUR_LIST: List[str] = ['EUR', 'USD']

parser = argparse.ArgumentParser(description='getting current currency')
parser.add_argument('--days', '-d', default=1, type=int, help='Number of days to see a currency')
parser.add_argument('--currency', '-c', default=CUR_LIST, type=str, help='Required type of currency')
args = vars(parser.parse_args())
days = args.get('days')
user_currency: str | list = args.get('currency')


def create_dates_list(number_days: int) -> List[str] | None:
    current_date = date.today()
    if number_days <= 10:
        return [(current_date - timedelta(days=i)).strftime('%d.%m.%Y') for i in range(number_days)]
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
            return {cur: dict(sale=el['saleRateNB'],
                              purchase=el['purchaseRateNB'])}
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


async def async_main(number_days: int) -> List:
    dates_list: list = create_dates_list(number_days)
    if dates_list:
        iter_response = create_response(dates_list)
        return await get_response(iter_response)


def handle_response(number_days: int, curr: str | List[str]) -> List:
    if curr != CUR_LIST:
        CUR_LIST.clear()
        CUR_LIST.append(curr)
    result_list_ = asyncio.run(async_main(number_days))
    if result_list_:
        return create_answer_sync(result_list_, CUR_LIST)


if __name__ == '__main__':
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    result = handle_response(days, user_currency)
    if result:
        for records in result:
            print(records)
