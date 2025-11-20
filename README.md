# berconpy

[![PyPI](https://img.shields.io/pypi/v/berconpy?label=View%20on%20pypi&style=flat-square)](https://pypi.org/project/berconpy/)
[![Docs](https://readthedocs.org/projects/berconpy/badge/?style=flat-square)](http://berconpy.readthedocs.io/)
[![](https://img.shields.io/github/actions/workflow/status/thegamecracks/berconpy/python-publish.yml?style=flat-square&logo=uv&label=build)](https://docs.astral.sh/uv/)
[![](https://img.shields.io/github/actions/workflow/status/thegamecracks/berconpy/python-test.yml?style=flat-square&logo=pytest&label=tests)](https://docs.pytest.org/en/stable/)
[![](https://img.shields.io/github/actions/workflow/status/thegamecracks/berconpy/ruff-check.yml?style=flat-square&logo=ruff&label=lints)](https://docs.astral.sh/ruff/)
[![](https://img.shields.io/github/actions/workflow/status/thegamecracks/berconpy/ruff-format.yml?style=flat-square&logo=ruff&label=style)](https://docs.astral.sh/ruff/)

An asynchronous Python wrapper over the [BattlEye RCON protocol][1].

## Features

- Easy to use event-based interface
- Automatic network loss recovery
- Included extension for Arma 3 commands and events

## Basic Usage

```py
import asyncio
import berconpy

client = berconpy.RCONClient()

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

## Migrating to v3

v3.0.0 is a major rewrite of this library to isolate generic BattlEye RCON functionality
from Arma 3 / DayZ-specific features. For users that need to work with other games like
Arma Reforger, you must use v3.

For v2 users that cannot migrate, ensure that your requirements are pinned
to `berconpy~=2.1` to prevent accidentally upgrading to v3.
[v2 documentation] is still available for the time being.

[v2 documentation]: https://berconpy.readthedocs.io/en/v2.1.4/

## Installation

(**Python 3.10** or higher is required)

This package can be installed from PyPI using the following command:

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
[2]: https://berconpy.readthedocs.io/en/stable/
[3]: https://github.com/thegamecracks/berconpy/blob/main/LICENSE
