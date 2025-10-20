# tools/run_budget.py
# Usage examples:
#   python3 -m tools.run_budget 8.8.8.8
#   python3 -m tools.run_budget 8.8.8.8 --per-hop-budget 6 --repeats-needed 3 --total-budget 50 --max-ttl 30
#   python3 -m tools.run_budget fake

import json
import argparse
from app.config import Settings
from app.brain.controller import BudgetController

def run_with_fake(args):
    from app.prober.fake import FakeProber
    script = {}
    for ttl in range(1, 5):
        script[(ttl, 0)] = [{
            "target": args.target or "8.8.8.8",
            "ttl": ttl, "flow_id": 0, "protocol": "udp-paris",
            "status": "ttl_exceeded", "hop_ip": f"10.0.0.{ttl}",
            "rtt_ms": 10.0 + ttl, "timestamp": None, "raw": {}
        }]
    script[(5, 0)] = [{
        "target": args.target or "8.8.8.8",
        "ttl": 5, "flow_id": 0, "protocol": "udp-paris",
        "status": "dest_reached", "hop_ip": args.target or "8.8.8.8",
        "rtt_ms": 40.0, "timestamp": None, "raw": {}
    }]

    p = FakeProber(script=script)
    s = Settings(
        method=args.method,
        max_ttl=args.max_ttl,
        per_hop_budget=args.per_hop_budget,
        repeats_needed=args.repeats_needed,
        total_budget=args.total_budget,
        flow_ids=tuple(args.flow_ids),
        pace_ms=args.pace_ms,
        use_sudo=args.use_sudo,
    )
    ctrl = BudgetController(p, s)
    res = ctrl.run(args.target or "8.8.8.8")
    print(json.dumps(res, indent=2))

def run_with_scamper(args):
    from app.prober.scamper import ScamperProber
    p = ScamperProber(
        use_sudo=args.use_sudo,
        method=args.method,
        pace_ms=args.pace_ms
    )
    s = Settings(
        method=args.method,
        max_ttl=args.max_ttl,
        per_hop_budget=args.per_hop_budget,
        repeats_needed=args.repeats_needed,
        total_budget=args.total_budget,
        flow_ids=tuple(args.flow_ids),
        pace_ms=args.pace_ms,
        use_sudo=args.use_sudo,
    )
    ctrl = BudgetController(p, s)
    res = ctrl.run(args.target)
    print(json.dumps(res, indent=2))

def build_argparser():
    ap = argparse.ArgumentParser(description="Budget-aware traceroute runner")
    ap.add_argument("target", nargs="?", help="Destination host/IP (or 'fake' to use FakeProber)")
    ap.add_argument("--method", default="udp-paris", choices=["udp-paris", "icmp-paris", "tcp"],
                    help="Probe method (Paris modes recommended)")
    ap.add_argument("--max-ttl", type=int, default=32, help="Maximum TTL to probe")
    ap.add_argument("--per-hop-budget", type=int, default=6, help="Max probes allowed per hop")
    ap.add_argument("--repeats-needed", type=int, default=3, help="Same IP replies needed to lock a hop")
    ap.add_argument("--total-budget", type=int, default=120, help="Global max number of probes")
    ap.add_argument("--flow-ids", type=int, nargs="+", default=[0, 1], help="Flow IDs to cycle (for ECMP peek)")
    ap.add_argument("--pace-ms", type=int, default=30, help="Base pacing between probes (milliseconds)")
    ap.add_argument("--use-sudo", action="store_true", default=True, help="Use sudo -n to run scamper")
    ap.add_argument("--no-sudo", dest="use_sudo", action="store_false", help="Disable sudo (only if caps set)")
    return ap

if __name__ == "__main__":
    ap = build_argparser()
    args = ap.parse_args()

    if args.target == "fake":
        run_with_fake(args)
    elif not args.target:
        ap.error("Provide a target (e.g., 8.8.8.8) or 'fake'")
    else:
        run_with_scamper(args)
