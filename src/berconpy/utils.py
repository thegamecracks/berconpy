import inspect
import struct

EMPTY = object()


async def maybe_coro(func, *args, **kwargs):
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    return func(*args, **kwargs)


def unpack_from(st: struct.Struct, data: bytes) -> tuple[tuple, bytes]:
    """Shorthand for unpacking a structure and returning the remaining bytes.

    :raises ValueError: An error occurred during unpacking.

    """
    try:
        return st.unpack_from(data), data[st.size:]
    except struct.error as e:
        raise ValueError(f'malformed data packet ({e})')
