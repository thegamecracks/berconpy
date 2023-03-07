import pytest

from berconpy import AsyncRCONClient
from berconpy.client import RCONClient


@pytest.fixture(params=[AsyncRCONClient])
def client(request: pytest.FixtureRequest) -> RCONClient:
    return request.param()
