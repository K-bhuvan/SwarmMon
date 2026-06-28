from swarmmon_agent.local_buffer import LocalBuffer


def test_local_buffer_drain():
    buf = LocalBuffer()
    buf.add({"event_type": "heartbeat"})
    buf.add({"event_type": "signal_freshness"})
    batch = buf.drain(10)
    assert len(batch) == 2
    assert len(buf) == 0
