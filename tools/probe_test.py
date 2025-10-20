# tools/probe_test.py
# Usage: python3 tools/probe_test.py 8.8.8.8 5
import sys
import json
from app.prober.scamper import ScamperProber

def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/probe_test.py <target_ip_or_host> [ttl]")
        return
    target = sys.argv[1]
    ttl = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    p = ScamperProber(use_sudo=True, pace_ms=40)
    ev = p.probe_once(target, ttl)
    print(json.dumps(ev, indent=2))

if __name__ == "__main__":
    main()
