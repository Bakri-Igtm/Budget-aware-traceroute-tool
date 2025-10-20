from dataclasses import dataclass

@dataclass
class Settings:
    method: str = "udp-paris"
    max_ttl: int = 32
    per_hop_budget: int = 6
    repeats_needed: int = 3
    total_budget: int = 120
    flow_ids: tuple[int, ...] = (0, 1)   # tiny ECMP peek
    pace_ms: int = 30                    # jitter around this
    use_sudo: bool = True                # WSL-friendly default
