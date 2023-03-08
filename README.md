# berconpy

[![PyPI](https://img.shields.io/pypi/v/berconpy?label=View%20on%20pypi&style=flat-square)](https://pypi.org/project/berconpy/)
[![Docs](https://readthedocs.org/projects/berconpy/badge/?style=flat-square)](http://berconpy.readthedocs.io/)

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

IP = "XXX.XXX.XXX.XXX"
PORT = 9999
PASSWORD = "ASCII_PASSWORD"

@client.dispatch.on_login
async def on_login():
    print("We have logged in!")

async def main():
    async with client.connect(IP, PORT, PASSWORD):
        players = await client.send_command("players")
        print(players)

asyncio.run(main())
```

See the [documentation][2] for more details.

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

This project uses the [MIT][3] License.

[1]: https://github.com/thegamecracks/berconpy/blob/main/docs/source/BERConProtocol.txt
[2]: http://berconpy.readthedocs.io/
[3]: https://github.com/thegamecracks/berconpy/blob/main/LICENSE
