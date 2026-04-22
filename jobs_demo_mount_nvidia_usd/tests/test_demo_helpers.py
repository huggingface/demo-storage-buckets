import demo


def test_parse_new_data_bytes_megabytes():
    stderr = (
        "Computing xorbs: 100%|#####| 2/2 [00:00<00:00]\n"
        "New Data Upload  : 100%|#####|  1.05MB / 1.05MB\n"
    )
    assert demo.parse_new_data_bytes(stderr) == int(1.05 * 1024 * 1024)


def test_parse_new_data_bytes_zero_bytes():
    stderr = "New Data Upload  : |#####|  0.00B / 0.00B\n"
    assert demo.parse_new_data_bytes(stderr) == 0


def test_parse_new_data_bytes_missing_returns_negative_one():
    assert demo.parse_new_data_bytes("nothing relevant here") == -1


def test_parse_new_data_bytes_uses_last_match():
    stderr = (
        "New Data Upload  : 50%|##|  0.10MB / 1.05MB\n"
        "New Data Upload  : 100%|#####|  1.05MB / 1.05MB\n"
    )
    assert demo.parse_new_data_bytes(stderr) == int(1.05 * 1024 * 1024)
