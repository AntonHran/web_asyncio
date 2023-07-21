import asyncio
import logging
from datetime import date, timedelta
from typing import List, Dict, Tuple, AsyncIterator, Coroutine
from datetime import datetime

import aiohttp
from aiopath import AsyncPath
import websockets
import names
from aiofile import async_open
from websockets import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosedOK


logging.basicConfig(level=logging.INFO)

privat_url = 'https://api.privatbank.ua/p24api/exchange_rates?json&date='

CUR_LIST: Tuple[str, str] = ('EUR', 'USD')


def parse_message(message: str) -> int:
    try:
        _, days = message.split(' ')
        return int(days.strip())
    except (TypeError, ValueError):
        return 1


def create_dates_list(days: int) -> List[str] | str:
    current_date = date.today()
    if days <= 10:
        return [(current_date - timedelta(days=i)).strftime('%d.%m.%Y') for i in range(days)]
    return 'You can not take info about currency for more than 10 days!'


async def get_request(url: str) -> dict | None:
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                print(f'Error status: {response.status} for {privat_url}')
                return None
        except aiohttp.ClientConnectionError as error:
            print(f'Connection error: {error} for {privat_url}')
        return None


async def create_response(dates: List[str]) -> AsyncIterator:
    for date_cur in dates:
        if await get_request(privat_url+date_cur):
            yield get_request(privat_url+date_cur)


async def get_response(response: AsyncIterator) -> List[Coroutine]:
    response_: List[AsyncIterator] = [res async for res in response if res]
    if response_:
        return await asyncio.gather(*response_)


async def async_form_answer(message: str) -> List | str:
    dates_str: List[str] = create_dates_list(parse_message(message))
    if type(dates_str) is str:
        return dates_str
    iter_response: AsyncIterator = create_response(dates_str)
    return await get_response(iter_response)


def parse_response(response: Dict) -> str:
    raw: str = response['date']
    for inner_dict in response['exchangeRate']:
        if inner_dict['currency'] in CUR_LIST:
            raw += f" {inner_dict['currency']}: (sale: {inner_dict['saleRateNB']}, " \
                   f"purchase: {inner_dict['purchaseRateNB']})"
    return raw


class Server:
    clients = set()

    async def register(self, ws: WebSocketServerProtocol):
        ws.name = names.get_full_name()
        self.clients.add(ws)
        logging.info(f'{ws.remote_address} connects')

    async def unregister(self, ws: WebSocketServerProtocol):
        self.clients.remove(ws)
        logging.info(f'{ws.remote_address} disconnects')

    async def send_to_clients(self, message: str):
        if self.clients:
            [await client.send(message) for client in self.clients]

    async def send_to_client(self, message: str, ws: WebSocketServerProtocol):
        await ws.send(message)

    async def ws_handler(self, ws: WebSocketServerProtocol):
        await self.register(ws)
        try:
            await self.distribute(ws)
        except ConnectionClosedOK:
            pass
        finally:
            await self.unregister(ws)

    async def handle_response(self, message: str) -> list:
        response_ = await async_form_answer(message)
        if type(response_) is str:
            return [response_]
        return [parse_response(response) for response in response_]

    async def distribute(self, ws: WebSocketServerProtocol):
        async for message in ws:
            if message.startswith('exchange'):
                for answer in await self.handle_response(message):
                    await log_to_file(message, answer, ws)
                    await self.send_to_client(answer, ws)
            else:
                await self.send_to_clients(f"{ws.name}: {message}")
                logging.info(f'{ws.remote_address} message: {message}')


async def log_to_file(request: str, response: str | list, ws: WebSocketServerProtocol) -> None:
    async with async_open(AsyncPath('.').joinpath('exchange.txt'), 'a', encoding='utf-8') as afw:
        await afw.write(f'{datetime.today()} | user: {ws.name} | request: {request} | response: {response}\n')


async def main():
    server = Server()
    async with websockets.serve(server.ws_handler, 'localhost', 8080):
        await asyncio.Future()  # run forever


if __name__ == '__main__':
    asyncio.run(main())
