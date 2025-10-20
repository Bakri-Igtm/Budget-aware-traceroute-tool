# app/brain/state.py
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Optional

@dataclass
class TTLState:
    counts: Counter = field(default_factory=Counter)  # hop_ip -> count
    timeouts: int = 0
    attempts: int = 0
    final: Optional[str] = None   # hop ip or "∅" or None if undecided
    confident: bool = False

@dataclass
class RunState:
    max_ttl: int
    total_budget: int
    ttl: int = 1
    probes_used: int = 0
    per_ttl: Dict[int, TTLState] = field(default_factory=dict)
    dest_reached: bool = False
    stop_reason: Optional[str] = None

    def __post_init__(self):
        for k in range(1, self.max_ttl + 1):
            self.per_ttl[k] = TTLState()
