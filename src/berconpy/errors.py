class RCONError(Exception):
    """The base class for RCON errors."""


class LoginFailure(RCONError):
    """Raised when either the RCON server could not respond to
    login attempts, or the password given to the server was incorrect.
    """


class RCONCommandError(RCONError):
    """Raised when an issue occurs during execution of an RCON command."""
