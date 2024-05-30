from typing import TypedDict

import pytest

from tests.models import Player, sample_players

from . import RCONClient, client


def test_update_players(client: RCONClient):
    """Checks that the cache can refresh itself from a "players" command."""
    cache = client.cache

    response = Player.make_message(sample_players)
    cache.update_players(response)

    assert len(cache.players) == len(sample_players)
    for player in sample_players:
        cached = cache.get_player(player.id)
        assert cached is not None
        for k, v in player.to_dict().items():
            assert getattr(cached, k) == v
