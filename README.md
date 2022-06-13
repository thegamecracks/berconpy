# berconpy

A (currently) asynchronous Python wrapper over the
[BattlEye RCON protocol][1].

## Installation

To install this package you must clone the repository,
either through git or manually downloading the files.

Using git:

```
pip install git+https://github.com/thegamecracks/berconpy
```

## Basic Usage

```py
import asyncio
import berconpy as rcon

client = rcon.AsyncRCONClient()

IP = 'XXX.XXX.XXX.XXX'
PORT = 9999
PASSWORD = 'ASCII_PASSWORD'


@client.listen()
async def on_login():
    print('We have logged in!')


async def main():
    async with client.connect(IP, PORT, PASSWORD):
        players = await client.send_command('players')
        print(players)


asyncio.run(main())
```

See the [examples](examples/) for more details.

## License

This project is under the [MIT](LICENSE) License.

[1]: https://www.battleye.com/downloads/BERConProtocol.txt
