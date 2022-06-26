# berconpy

An asynchronous Python wrapper over the
[BattlEye RCON protocol][1].

## Features

- Easy to use event-based interface
- Automatic recovery from network loss
- Included extension for using Arma-related commands

## Basic Usage

```py
import asyncio
import berconpy

client = berconpy.AsyncRCONClient()

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

Further documentation can be found in the [source code][2].

## Installation

(**Python 3.10** or higher is required)

This package be installed by cloning this repository,
either with git or by manual download.

With git and pip installed:

```
pip install git+https://github.com/thegamecracks/berconpy
```

Manual installation with pip:

1. Download and unzip the repository
2. Open a terminal inside the unzipped directory
3. Run the following command:
   - Windows: `py -m pip install .`
   - Linux: `python3 -m pip install .`

## Related resources
- [BattlEye RCON protocol specification][1]
- [BattlEye RCON commands](https://www.battleye.com/support/documentation/)
- [Arma server commands](https://community.bistudio.com/wiki/Multiplayer_Server_Commands)

## License

This project uses the [MIT](LICENSE) License.

[1]: https://www.battleye.com/downloads/BERConProtocol.txt
[2]: https://github.com/thegamecracks/berconpy/blob/main/src/berconpy/client.py
