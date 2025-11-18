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
    True if this hop looks genuinely unstable and might deserve extra probes:
    - at least 2 timeouts (lots of silence), OR
    - 3 or more distinct IPs (heavy ECMP / flapping)
    """
    many_timeouts = tstate.timeouts >= 2
    heavy_ecmp = len(tstate.counts) >= 3
    return many_timeouts or heavy_ecmp