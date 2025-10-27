import pytest

from berconpy.protocol import RCONClientProtocol, RCONServerProtocol

from . import expected_password


@pytest.fixture
def client() -> RCONClientProtocol:
    return RCONClientProtocol()


@pytest.fixture
def server() -> RCONServerProtocol:
    return RCONServerProtocol(password=expected_password)
