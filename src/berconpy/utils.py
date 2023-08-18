import inspect
from typing import Awaitable, Callable, Iterable, ParamSpec, TypeVar

EMPTY = object()
P = ParamSpec("P")
T = TypeVar("T")

MaybeCoroFunc = Callable[P, T | Awaitable[T]]


def copy_doc(original: Callable) -> Callable[[T], T]:
    def decorator(new: T) -> T:
        new.__doc__ = original.__doc__
        return new

    return decorator


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


async def maybe_coro(
    func: MaybeCoroFunc[P, T],
    *args: P.args,
    **kwargs: P.kwargs,
) -> T:
    ret = func(*args, **kwargs)
    if inspect.isawaitable(ret):
        return await ret
    return ret  # type: ignore
