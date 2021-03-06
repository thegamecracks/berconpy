import inspect
from typing import Any, Callable, Coroutine, Iterable, TypeVar

EMPTY = object()
T = TypeVar('T')

CoroFunc = Callable[[...], Coroutine]
MaybeCoroFunc = CoroFunc | Callable


def find(iterable: Iterable[T], predicate: Callable[[T], bool]) -> T | None:
    """Returns the first item in the iterable where the given predicate returns True."""
    for item in iterable:
        if predicate(item):
            return item


def get(iterable: Iterable[T], **attrs) -> T | None:
    """Returns the first item in the iterable that matches the given attributes."""
    def predicate(item: T):
        for attr, expected in attrs.items():
            value = getattr(item, attr)
            if value != expected:
                return False
        return True

    return find(iterable, predicate)


async def maybe_coro(func, *args, **kwargs):
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    return func(*args, **kwargs)
