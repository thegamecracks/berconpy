"""Connects to an RCON server and allows typing in any command."""
import asyncio

import berconpy as rcon

IP_ADDR = 'XXX.XXX.XXX.XXX'
PORT = 9999
PASSWORD = 'ASCII_PASSWORD'

client = rcon.AsyncRCONClient('repl.py')


async def ainput():
    return await asyncio.to_thread(input)


@client.listen()
async def on_message(message: str):
    print(message)


async def main():
    async with client.connect(IP_ADDR, PORT, PASSWORD):
        print(await client.send_command('commands'))
        while True:
            command = await ainput()
            response = await client.send_command(command)
            print(response)


if __name__ == '__main__':
    asyncio.run(main())
