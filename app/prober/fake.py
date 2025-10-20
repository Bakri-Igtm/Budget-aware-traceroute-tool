# app/prober/fake.py
from app.prober.base import Prober, ProbeEvent
from collections import deque

class FakeProber(Prober):
    """
    script: dict[(ttl,flow_id)] -> deque of ProbeEvent-like dicts to return each call
    If no scripted event left, returns a timeout event.
    """
    def __init__(self, script=None):
        self.script = {}
        if script:
            for k, v in script.items():
                self.script[k] = deque(v)

    def probe_once(self, dest: str, ttl: int, flow_id: int = 0) -> ProbeEvent:
        key = (ttl, flow_id)
        dq = self.script.get(key)
        if dq and len(dq) > 0:
            return dq.popleft()
        # default: timeout
        return {
            "target": dest,
            "ttl": ttl,
            "flow_id": flow_id,
            "protocol": "udp-paris",
            "status": "timeout",
            "hop_ip": None,
            "rtt_ms": None,
            "timestamp": None,
            "raw": {}
        }
