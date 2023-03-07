from typing import Generic, TypeVar

from ..errors import RCONError

T = TypeVar("T")


class InvalidStateError(RCONError, Generic[T]):
    """The current state of the protocol does not match the expected states."""

    current_state: T
    """The current state of the protocol."""
    expected_states: tuple[T]
    """A tuple of states that the protocol was expecting to be in."""

    def __init__(self, current_state: T, expected_states: tuple[T, ...]):
        self.current_state = current_state
        self.expected_states = expected_states
        super().__init__(
            "protocol state must be one of {}, received {} instead".format(
                ", ".join(str(s) for s in self.expected_states),
                self.current_state,
            )
        )
