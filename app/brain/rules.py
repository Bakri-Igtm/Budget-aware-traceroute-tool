# app/brain/rules.py
from collections import Counter

def confident_rule(counts: Counter, repeats_needed: int) -> bool:
    if not counts: 
        return False
    top = max(counts.values())
    return top >= repeats_needed

def dark_rule(timeouts: int, attempts: int, cap: int) -> bool:
    """
    Decide the hop is 'dark' if we're near/at cap and most attempts are silence.
    Slightly aggressive: if attempts >= min(3, cap) and timeouts >= attempts - 1
    """
    if attempts >= min(3, cap) and timeouts >= attempts - 1:
        return True
    if attempts >= cap:
        return True
    return False

def uncertain(tstate) -> bool:
    """
    True if this hop looks unstable and may need extra probes:
    - at least one timeout, OR
    - multiple distinct IPs seen and not yet confident
    """
    multi_ip = len(tstate.counts) >= 2
    some_timeouts = tstate.timeouts >= 1
    return some_timeouts or multi_ip
