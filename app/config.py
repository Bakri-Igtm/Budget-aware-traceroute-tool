from dataclasses import dataclass

@dataclass
class Settings:
    method: str = "udp-paris"
    max_ttl: int = 32
    per_hop_budget: int = 6
    repeats_needed: int = 2
    total_budget: int = 120
    flow_ids: tuple[int, ...] = (0, 1)
    pace_ms: int = 30
    use_sudo: bool = True

    # NEW: rollover credit tuning
    rollover_cap_per_hop: int = 2     # max extra credits you can add to a single hop
    hard_per_hop_max: int = 6         # hard ceiling for attempts even with rollover
    rollover_pool_max: int = 10       # don’t hoard infinite credits

    # (optional) adaptive wait toggle for later prober tuning
    adaptive_wait: bool = False
