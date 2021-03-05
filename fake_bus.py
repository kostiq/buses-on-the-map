import functools
import itertools
import json
import logging
import os
import random
import uuid
from contextlib import AsyncExitStack
from dataclasses import asdict

import asyncclick as click
import trio
from trio_websocket import open_websocket_url, HandshakeError

from model import Bus


def load_routes(directory_path='routes'):
    for filename in os.listdir(directory_path):
        if filename.endswith('.json'):
            filepath = os.path.join(directory_path, filename)
            with open(filepath, 'r', encoding='utf8') as file:
                yield json.load(file)


def generate_bus_id(route_id, bus_index, emulator_id):
    return f'{route_id}-{bus_index}-{emulator_id}'


def relaunch_on_disconnect(async_function):
    @functools.wraps(async_function)
    async def wrapper(*args, **kwargs):
        while True:
            try:
                await async_function(*args, **kwargs)
            except HandshakeError:
                logging.error('Connection to server lost, reconnecting in 1 sec...')
                await trio.sleep(1)

    return wrapper


async def run_bus(send_channel, json_data, emulator_id, bus_count=1):
    coordinates = json_data['coordinates']
    coordinates_length = len(coordinates)

    buses_offset = [random.randint(0, coordinates_length) for _ in range(bus_count)]

    async with send_channel:
        for index in itertools.cycle(range(coordinates_length)):
            for bus_index in range(bus_count):
                lat, lng = coordinates[index - buses_offset[bus_index]]
                bus_id = generate_bus_id(json_data['name'], bus_index, emulator_id)
                bus = Bus(bus_id, lat, lng, json_data['name'])

                message = json.dumps(asdict(bus), ensure_ascii=False)

                logging.info(f'send to channel {message}')
                await send_channel.send(message)


@relaunch_on_disconnect
async def send_updates(server_address, receive_channel, websocket_number, refresh_timeout):
    async for value in receive_channel:
        async with AsyncExitStack() as stack:
            sockets = [await stack.enter_async_context(open_websocket_url(server_address))
                       for _ in range(websocket_number)]
            try:
                await random.choice(sockets).send_message(value)
                await trio.sleep(refresh_timeout)
            except OSError as ose:
                logging.error(f'Connection attempt failed: {ose}')


@click.command()
@click.option('-s', '--server', default='ws://127.0.0.1:8080', help='Server url.')
@click.option('-r', '--route_number', default=20, help='Number of bus routes.')
@click.option('-b', '--buses_per_route', default=3, help='Number of buses on route.')
@click.option('-w', '--websocket_number', default=5, help='Number of opened websockets.')
@click.option('-eid', '--emulator_id', default=uuid.uuid4(), help='Unique emulator prefix')
@click.option('-t', '--refresh_timeout', default=0.1, help='Timeout between messages to server.')
@click.option('-v', count=True, help='Verbosity.')
async def main(server, route_number, buses_per_route, websocket_number, emulator_id, refresh_timeout, v):
    logging_params = dict(
        format='%(asctime)s %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    if v:
        logging_params['level'] = 'INFO'

    logging.basicConfig(**logging_params)

    async with trio.open_nursery() as nursery:
        send_channel, receive_channel = trio.open_memory_channel(0)
        nursery.start_soon(send_updates, server, receive_channel, websocket_number, refresh_timeout)
        for json_data in list(load_routes())[:route_number]:
            nursery.start_soon(run_bus, send_channel, json_data, emulator_id, buses_per_route)


if __name__ == '__main__':
    main(_anyio_backend='trio')
