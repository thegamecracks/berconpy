import pytest

from berconpy import RCONClient
from berconpy.client import RCONClient


@pytest.fixture(params=[RCONClient])
def client(request: pytest.FixtureRequest) -> RCONClient:
    return request.param()
