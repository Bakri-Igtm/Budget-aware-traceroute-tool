# app/brain/state.py
from collections import Counter
from dataclasses import dataclass, field

@dataclass
class TtlState:
    final: str | None = None
    counts: Counter = field(default_factory=Counter)
    timeouts: int = 0
    attempts: int = 0
    confident: bool = False
    # debug meta for reporting (optional)
    base_cap: int = 0
    dyn_cap: int = 0
    pool_in: int = 0     # credits deposited at hop exit
    pool_out: int = 0    # credits spent beyond base at this hop

@dataclass
class RunState:
    max_ttl: int
    total_budget: int
    ttl: int = 1
    probes_used: int = 0
    stop_reason: str | None = None
    dest_reached: bool = False
    # NEW: global credit pool
    pool: int = 0
    # per-ttl book-keeping
    per_ttl: dict = field(default_factory=dict)

    def __post_init__(self):
        for k in range(1, self.max_ttl + 1):
            self.per_ttl[k] = TtlState()
