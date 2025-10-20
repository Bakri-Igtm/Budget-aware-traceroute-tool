# tools/regular_trace.py
# Usage:
#   python3 -m tools.regular_trace <target> [q] [method]
# Examples:
#   python3 -m tools.regular_trace 8.8.8.8
#   python3 -m tools.regular_trace 8.8.8.8 3
#   python3 -m tools.regular_trace 8.8.8.8 5 icmp-paris
#
# Notes:
# - Runs scamper with sudo -n (NOPASSWD rule for /usr/bin/scamper recommended).
# - Outputs a JSON summary with path, per-TTL reply counts, and estimated probes used.

import sys
import json
import shlex
import subprocess
from collections import defaultdict, Counter

def run_scamper_full_trace(target: str, q: int = 3, method: str = "udp-paris"):
    # Build scamper command: target via -i, template via -c
    # Paris mode keeps flow tuple stable across probes
    cmd = f"sudo -n scamper -O json -i {shlex.quote(target)} -c 'trace -P {method} -q {q} -g 10 -G 2'"
    proc = subprocess.run(cmd, shell=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = proc.stdout

    trace_obj = None
    # Scamper prints multiple JSON lines (cycle-start / trace / cycle-stop)
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "trace":
            trace_obj = obj
            break

    if trace_obj is None:
        # Surface a helpful snippet for debugging
        raise RuntimeError(f"Could not parse scamper 'trace' JSON.\nOutput (first 500 chars):\n{out[:500]}")

    return trace_obj, out, q

def summarize_trace(trace_obj: dict, q_assumed: int = 3) -> dict:
    """
    Summarize the scamper 'trace' JSON into:
    - path: majority IP per TTL, else '∅'
    - per_ttl_counts: counts of replying IPs per TTL
    - probes_used_est: q_assumed * number of TTLs probed (firsthop..hoplimit)
    """
    hops = trace_obj.get("hops", []) or []

    # Aggregate replies by TTL
    by_ttl = defaultdict(list)
    for h in hops:
        ttl = h.get("probe_ttl") or h.get("ttl")
        if ttl is None:
            continue
        addr = h.get("addr")
        if addr:
            by_ttl[ttl].append(addr)

    firsthop = trace_obj.get("firsthop", 1)
    hoplimit = trace_obj.get("hoplimit")
    if not hoplimit:
        # Fallback to max TTL observed in replies
        hoplimit = max(by_ttl.keys()) if by_ttl else firsthop

    # Majority path + counts
    path = {}
    per_ttl_counts = {}
    for ttl in range(firsthop, hoplimit + 1):
        cnt = Counter(by_ttl.get(ttl, []))
        per_ttl_counts[ttl] = dict(cnt)
        path[ttl] = (max(cnt, key=cnt.get) if cnt else "∅")

    # Stop reason
    stop_reason = trace_obj.get("stop_reason") or "UNKNOWN"

    # Estimated probes = q * TTLs probed (conventional traceroute behavior)
    total_ttls = max(0, hoplimit - firsthop + 1)
    probes_used_est = q_assumed * total_ttls

    return {
        "target": trace_obj.get("dst"),
        "method": trace_obj.get("method"),
        "firsthop": firsthop,
        "last_ttl_probed": hoplimit,
        "stop_reason": stop_reason,
        "probes_used_est": probes_used_est,
        "path": path,
        "per_ttl_counts": per_ttl_counts,
    }

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 -m tools.regular_trace <target> [q] [method]")
        sys.exit(1)

    target = sys.argv[1]
    q = int(sys.argv[2]) if len(sys.argv) >= 3 else 3
    method = sys.argv[3] if len(sys.argv) >= 4 else "udp-paris"

    trace_obj, raw, q_used = run_scamper_full_trace(target, q=q, method=method)
    summary = summarize_trace(trace_obj, q_assumed=q_used)
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
