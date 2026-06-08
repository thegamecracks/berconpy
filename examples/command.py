"""Sends a command to an RCON server."""

import asyncio
import logging

import berconpy

IP_ADDR = "XXX.XXX.XXX.XXX"
PORT = 9999
PASSWORD = "ASCII_PASSWORD"

log = logging.getLogger("berconpy")
log.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
)
log.addHandler(handler)

client = berconpy.RCONClient()


async def main():
    async with client.connect(IP_ADDR, PORT, PASSWORD):
        response = await client.send_command("players")
        print(response)


if __name__ == "__main__":
    asyncio.run(main())
