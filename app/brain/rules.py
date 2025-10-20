# app/brain/rules.py
from typing import Dict
from collections import Counter

def top_count(counts: Counter) -> int:
    return max(counts.values()) if counts else 0

def confident_rule(counts: Counter, repeats_needed: int) -> bool:
    """
    Return True if any hop ip has been seen at least repeats_needed times.
    """
    return top_count(counts) >= repeats_needed

def dark_rule(timeouts: int, attempts: int, per_hop_budget: int) -> bool:
    """
    Return True if we consider the hop dark (non-responsive).
    Simple rule: attempts >= per_hop_budget and timeouts >= (per_hop_budget - 1)
    (i.e., almost all attempts timed out).
    """
    if attempts < per_hop_budget:
        return False
    return timeouts >= max(1, per_hop_budget - 1)

def should_stop_run(run_state) -> bool:
    """
    Stop if destination reached, total budget used, or exceeded TTL.
    """
    if run_state.dest_reached:
        run_state.stop_reason = "dest_reached"
        return True
    if run_state.probes_used >= run_state.total_budget:
        run_state.stop_reason = "budget_exhausted"
        return True
    if run_state.ttl > run_state.max_ttl:
        run_state.stop_reason = "max_ttl"
        return True
    return False
