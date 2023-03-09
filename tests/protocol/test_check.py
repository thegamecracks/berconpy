from berconpy.protocol import ClientMessagePacket, NonceCheck


def test_nonce_check_unit():
    """Asserts that NonceCheck has a rolling window of accepted sequences."""
    n = 5
    check = NonceCheck(n)
    assert check.max_size == n

    for end in range(1, 256):
        for i in range(max(0, end - n), end):
            if i + 1 == end:
                assert check(ClientMessagePacket(i))
            else:
                assert not check(ClientMessagePacket(i))
