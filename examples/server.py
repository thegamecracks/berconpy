"""A test script for simulating an RCON client/server connection."""
import asyncio
import logging

import berconpy as rcon
import berconpy.server as rcon_server

IP_ADDR = '127.0.0.1'
PORT = 9999
PASSWORD = 'ASCII_PASSWORD'

log = logging.getLogger('berconpy')
log.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
log.addHandler(handler)

server = rcon_server.AsyncRCONServer(password=PASSWORD)
client = rcon.AsyncRCONClient()


async def main():
    server_task = asyncio.create_task(server.host(IP_ADDR, PORT))

    async with client.connect(IP_ADDR, PORT, PASSWORD):
        await client.send_command('players')

    server_task.cancel()


if __name__ == '__main__':
    asyncio.run(main())
