from typing import Literal, TypedDict, Optional

ReplyType = Literal["ttl_exceeded", "dest_reached", "unreach", "timeout"]

class ProbeEvent(TypedDict, total=False):
    target: str
    ttl: int
    flow_id: int
    protocol: str
    status: ReplyType
    hop_ip: Optional[str]
    rtt_ms: Optional[float]
    timestamp: str
    raw: dict  # original scamper JSON line for debug
