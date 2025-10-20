# app/prober/base.py
from abc import ABC, abstractmethod
from typing import TypedDict, Optional

class ProbeEvent(TypedDict, total=False):
    target: str
    ttl: int
    flow_id: int
    protocol: str
    status: str                 # "ttl_exceeded" | "dest_reached" | "timeout" | "unreach"
    hop_ip: Optional[str]
    rtt_ms: Optional[float]
    timestamp: str
    raw: dict

class Prober(ABC):
    @abstractmethod
    def probe_once(self, dest: str, ttl: int, flow_id: int = 0) -> ProbeEvent:
        """Send exactly one probe for dest@ttl and return a ProbeEvent dict."""
        raise NotImplementedError
