import collections
from typing import Generic, Protocol, TypeVar

from .packet import Packet

__all__ = (
    "Check",
    "NonceCheck",
)

P_contra = TypeVar("P_contra", contravariant=True)


class Check(Protocol, Generic[P_contra]):
    """A callable object that makes a boolean judgement about a packet."""

    def __call__(self, packet: P_contra, /) -> bool:
        raise NotImplementedError

    def reset(self) -> None:
        """Resets the check's state."""
        raise NotImplementedError


class NonceCheck:
    """A simple check that verifies the :py:attr:`Packet.sequence`
    has not been recently seen before.

    :param max_size:
        Specifies the max size to use for the internal deque to keep
        track of indices. Since the range of a packet's sequence is only 256,
        a max size matching or exceeding that will eventually lead to this
        check infinitely returning False, and as such a :py:exc`:`ValueError`
        is raised to prevent that from occurring.

    """

    def __init__(self, max_size: int):
        self.deque = collections.deque((), max_size)

    def __call__(self, packet: Packet) -> bool:
        if packet.sequence in self.deque:
            return False

        self.deque.append(packet.sequence)
        return True

    def reset(self) -> None:
        self.deque.clear()

    @property
    def max_size(self) -> int:
        assert self.deque.maxlen is not None
        return self.deque.maxlen
