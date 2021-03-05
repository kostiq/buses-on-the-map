import functools
import json
import logging
from contextlib import suppress

import asyncclick as click
import trio
from trio_websocket import serve_websocket, ConnectionClosed

from model import WindowBounds

buses = dict()
bounds = WindowBounds()


def check_bus_message(message):
    try:
        json_message = json.loads(message)
    except json.JSONDecodeError:
        return {"errors": ["Requires valid JSON"], "msgType": "Errors"}

    missed_keys = {'busId', 'lat', 'lng', 'route'} - set(json_message.keys())
    if missed_keys:
        return {"errors": [f"Requires {','.join(missed_keys)} specified"], "msgType": "Errors"}


def check_client_message(message):
    try:
        json_message = json.loads(message)
    except json.JSONDecodeError:
        return {"errors": ["Requires valid JSON"], "msgType": "Errors"}

    if json_message.get('msgType') != 'newBounds':
        return {"errors": ["Requires msgType specified"], "msgType": "Errors"}


def filter_buses(buses, bounds):
    for bus in buses:
        if bounds.is_inside(bus['lat'], bus['lng']):
            yield bus


async def listen_browser(ws, bounds):
    while True:
        try:
            message = await ws.get_message()
            logging.info(f'get from client {message}')
            invalid = check_client_message(message)
            if invalid:
                logging.info(f'Response: {invalid}')
                await ws.send_message(json.dumps(invalid))
                continue

            window_bounds = json.loads(message)['data']
            logging.info(message)
            bounds.update(**window_bounds)

            await trio.sleep(1)

        except ConnectionClosed:
            logging.error('Browser closed')
            break


async def send_buses(ws, bounds):
    while True:
        try:
            buses_in_window = list(filter_buses(buses.values(), bounds))
            message_to_browser = {
                "msgType": "Buses",
                "buses": buses_in_window
            }
            if buses_in_window:
                logging.info(f'sent to browser {message_to_browser}')
                await ws.send_message(json.dumps(message_to_browser))

            await trio.sleep(1)
        except ConnectionClosed:
            break


async def get_fake_bus_info(request):
    ws = await request.accept()
    while True:
        try:
            message = await ws.get_message()
            invalid = check_bus_message(message)
            logging.info(f'get from buses {message}')
            if invalid:
                logging.info(f'Response: {invalid}')
                await ws.send_message(json.dumps(invalid))
                continue

            json_message = json.loads(message)
            bus_id = json_message['busId']
            buses[bus_id] = json_message

        except ConnectionClosed:
            break


async def talk_to_browser(request):
    ws = await request.accept()
    async with trio.open_nursery() as nursery:
        nursery.start_soon(listen_browser, ws, bounds)
        nursery.start_soon(send_buses, ws, bounds)


@click.command()
@click.option('--bus_port', default=8080, help='Port for bus emulator.')
@click.option('--browser_port', default=8000, help='Number of bus routes.')
@click.option('-v', count=True, help='Verbosity.')
async def main(bus_port, browser_port, v):
    logging_params = dict(
        format='%(asctime)s %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    if v:
        logging_params['level'] = 'INFO'

    logging.basicConfig(**logging_params)

    async with trio.open_nursery() as nursery:
        nursery.start_soon(
            functools.partial(serve_websocket, get_fake_bus_info, '127.0.0.1', bus_port, ssl_context=None)
        )
        nursery.start_soon(
            functools.partial(serve_websocket, talk_to_browser, '127.0.0.1', browser_port, ssl_context=None)
        )


if __name__ == '__main__':
    with suppress(KeyboardInterrupt):
        main(_anyio_backend='trio')
