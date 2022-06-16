# berconpy

An asynchronous Python wrapper over the
[BattlEye RCON protocol][1].

## Features

- Easy-to-use event based client interface
- Automatic server timeout recovery
- Built-in extension for Arma RCON

## Requirements

- **Python 3.10** or higher

## Installation

To install this package you must clone the repository,
either through git or by manually downloading the files.

Using git:

```
pip install git+https://github.com/thegamecracks/berconpy
```

Manual installation:

1. Download and unzip the repository
2. Open a terminal inside the new directory
3. Run the following command:
  - Windows: `py -m pip install .`
  - Linux: `python3 -m pip install .`

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

This project uses the [MIT](LICENSE) License.

[1]: https://www.battleye.com/downloads/BERConProtocol.txt
