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


def test_build_job_url_with_namespace():
    assert (
        demo.build_job_url("rajatarya", "abc123def")
        == "https://huggingface.co/jobs/rajatarya/abc123def"
    )


import pytest


def _inspector_from_sequence(statuses):
    """Returns an inspector callable that yields one status per call."""
    it = iter(statuses)

    def inspect(_job_id):
        return next(it)
    return inspect


def test_poll_job_succeeds(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _s: None)
    inspector = _inspector_from_sequence(["pending", "running", "succeeded"])
    result = demo.poll_job(
        job_id="abc", poll_interval=0.01, timeout=30, inspector=inspector
    )
    assert result.status == "succeeded"
    assert result.elapsed_s >= 0


def test_poll_job_fails(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _s: None)
    inspector = _inspector_from_sequence(["running", "failed"])
    result = demo.poll_job(
        job_id="abc", poll_interval=0.01, timeout=30, inspector=inspector
    )
    assert result.status == "failed"


def test_poll_job_cancelled(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _s: None)
    inspector = _inspector_from_sequence(["cancelled"])
    result = demo.poll_job(
        job_id="abc", poll_interval=0.01, timeout=30, inspector=inspector
    )
    assert result.status == "cancelled"


def test_poll_job_times_out(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _s: None)
    monotonic_vals = iter([0.0, 0.1, 0.2, 99.0])
    monkeypatch.setattr("time.monotonic", lambda: next(monotonic_vals))
    inspector = lambda _j: "running"
    result = demo.poll_job(
        job_id="abc", poll_interval=0.01, timeout=1.0, inspector=inspector
    )
    assert result.status == "timeout"


def test_poll_job_keyboard_interrupt_returns_interrupted(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _s: None)

    def inspect(_j):
        raise KeyboardInterrupt

    result = demo.poll_job(
        job_id="abc", poll_interval=0.01, timeout=30, inspector=inspect
    )
    assert result.status == "interrupted"
