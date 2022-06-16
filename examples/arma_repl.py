"""Demonstrates the Arma RCON extension."""
import asyncio
import logging

from berconpy.ext.arma import AsyncArmaRCONClient

IP_ADDR = 'XXX.XXX.XXX.XXX'
PORT = 9999
PASSWORD = 'ASCII_PASSWORD'

log = logging.getLogger('berconpy')
log.setLevel(logging.WARNING)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
log.addHandler(handler)

client = AsyncArmaRCONClient(__name__)


async def ainput():
    return await asyncio.to_thread(input)


@client.listen()
async def on_admin_login(admin_id: int, addr: str):
    print(f'Admin #{admin_id} logged in')


@client.listen()
async def on_player_connect(player_id: int, name: str, addr: str):
    print(f'Player #{player_id} {name} connected')


@client.listen()
async def on_player_disconnect(player_id: int, name: str):
    print(f'Player #{player_id} {name} disconnected')


@client.listen()
async def on_player_kick(player_id: int, name: str, guid: str, reason: str):
    print(f'Player #{player_id} {name} was kicked: {reason}')


@client.listen()
async def on_admin_message(admin_id: int, channel: str, message: str):
    print(f'({channel}) Admin #{admin_id}: {message}')


@client.listen()
async def on_player_message(channel: str, name: str, message: str):
    print(f'({channel}) {name}: {message}')


async def main():
    async with client.connect(IP_ADDR, PORT, PASSWORD):
        print(await client.send_command('commands'))

        while True:
            command = await ainput()

            if command.lower() == '#players':
                for p in client.players:
                    print(p)
            else:
                response = await client.send_command(command)
                print(response)


if __name__ == '__main__':
    asyncio.run(main())
