import asyncio


class RCONError(Exception):
    """The base class for RCON errors."""


class LoginFailure(RCONError):
    """Raised when the client could not log into the RCON server."""


class LoginRefused(LoginFailure):
    """Raised when the password given to the RCON server was incorrect."""


class LoginTimeout(LoginFailure, asyncio.TimeoutError):
    """Raised when the RCON server could not respond to our login attempts."""


class RCONCommandError(RCONError):
    """Raised when an issue occurs during execution of an RCON command."""
