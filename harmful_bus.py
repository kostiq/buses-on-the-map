import logging

import trio
from trio_websocket import open_websocket_url


async def main():
    try:
        async with open_websocket_url('ws://127.0.0.1:8080') as ws:
            await ws.send_message('{"test": 1}')
            message = await ws.get_message()
            logging.info('Received message: %s', message)

    except OSError as ose:
        logging.error('Connection attempt failed: %s', ose)


if __name__ == '__main__':
    logging.basicConfig(
        level='INFO',
        format='%(asctime)s %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    trio.run(main)

