# berconpy

An asynchronous Python wrapper over the
[BattlEye RCON protocol][1].

## Features

- Easy to use event-based interface
- Automatic network loss recovery
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

This package can be installed from PyPi using the following command:

```
# Linux/macOS
python3 -m pip install berconpy

# Windows
py -m pip install berconpy
```

If you want to install the development version instead, and you have git installed:

```
pip install git+https://github.com/thegamecracks/berconpy
```

## Related resources

- [BattlEye RCON protocol specification][1]
- [BattlEye RCON commands](https://www.battleye.com/support/documentation/)
- [Arma server commands](https://community.bistudio.com/wiki/Multiplayer_Server_Commands)

## License

This project uses the [MIT](LICENSE) License.

[1]: https://www.battleye.com/downloads/BERConProtocol.txt
[2]: https://github.com/thegamecracks/berconpy/blob/main/src/berconpy/client.py
