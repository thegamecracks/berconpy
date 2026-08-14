"""An example of sending and receiving responses from Arma Reforger.

Arma Reforger has made the majority of command responses asynchronous,
meaning that instead of sending the responses over a COMMAND event,
they are immediately acknowledged with an empty COMMAND and eventually
responded across one or more MESSAGE events.

Some Arma 3 commands are also implementing this strategy, like #mpmissions.

This means the ``RCONClient.send_command()`` method is no longer able to
identify which response corresponds to which command.

Instead of relying on COMMAND, this example uses a queue to concatenate
responses. Because Arma Reforger processes each command one at a time,
we can send a dummy 'hello' command to signal the termination of each response.

From your code's perspective, the ``send_command()`` function should work
identically to ``RCONClient.send_command()``.

"""

import asyncio
from collections import deque
from dataclasses import dataclass, field

import berconpy

HOST = "127.0.0.1"
PORT = 2303
PASSWORD = "ASCII_PASSWORD"

client = berconpy.RCONClient()


async def main():
    async with client.connect(HOST, PORT, PASSWORD):
        # Test running two commands concurrently
        ban_list, players = await asyncio.gather(
            asyncio.wait_for(send_command("ban list"), timeout=5),
            asyncio.wait_for(send_command("players"), timeout=5),
        )
        print(repr(ban_list))
        print(repr(players))


async def send_command(command: str) -> str:
    fut = asyncio.get_running_loop().create_future()
    seq = MessageSequence(fut)
    _message_queue.append(seq)

    async with _command_lock:
        await client.send_command(command)
        await client.send_command("hello")

    return await fut


@client.dispatch.on_message
async def on_message(message: str) -> None:
    if not _message_queue:
        return
    elif message == "Processing Command: hello":  # Reforger-specific
        pass
    elif message == "unknown command 'hello'":  # Reforger-specific
        seq = _message_queue.popleft()
        if not seq.fut.done():
            seq.fut.set_result("\n".join(seq.messages))
    else:
        _message_queue[0].messages.append(message)


@dataclass
class MessageSequence:
    fut: asyncio.Future[str]
    """The future to be resolved at the end of a command's response."""
    messages: list[str] = field(default_factory=list)
    """The intermediate messages to be concatenated for ``fut``."""


_command_lock = asyncio.Lock()
_message_queue: deque[MessageSequence] = deque()


if __name__ == "__main__":
    asyncio.run(main())
