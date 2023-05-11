import collections
from typing import Generic, Protocol, TypeVar

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


class Sequential(Protocol):
    """An object that has a "sequence" integer attribute."""

    @property
    def sequence(self) -> int:
        ...


class NonceCheck:
    """A simple check that verifies the :py:attr:`Packet.sequence`
    has not been recently seen before.

    :param max_size:
        The maximum number of sequences to keep track of.
        After N unique sequences are received, each unique sequence that
        follows will cause the first (i.e. oldest) sequence to be dropped.
        Since a packet's sequence can only have 256 different values,
        a :py:exc:`ValueError` is raised if the max size is set to 256
        or greater.

    """

    deque: collections.deque[int]

    def __init__(self, max_size: int):
        if max_size not in range(256):
            raise ValueError(f"max_size must be within 0-255, not {max_size!r}")
        self.deque = collections.deque((), max_size)

    def __call__(self, packet: Sequential) -> bool:
        if packet.sequence in self.deque:
            return False

        self.deque.append(packet.sequence)
        return True

    def reset(self) -> None:
        self.deque.clear()

    @property
    def max_size(self) -> int:
        """The maximum number of sequences that the check can keep track of."""
        assert self.deque.maxlen is not None
        return self.deque.maxlen
