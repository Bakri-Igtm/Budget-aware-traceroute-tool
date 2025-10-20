# app/prober/scamper.py
import json
import os
import random
import shlex
import shutil
import subprocess
import time
from datetime import datetime
from typing import Optional

from app.prober.base import Prober, ProbeEvent

DEFAULT_SCAMPER_BIN = shutil.which("scamper") or "/usr/bin/scamper"

class ScamperProber(Prober):
    """
    Simple wrapper around the 'scamper' binary to send a single-TTL Paris-style probe
    and return a normalized ProbeEvent. It will try non-sudo first and fall back to sudo -n.
    """

    def __init__(self,
                 scamper_bin: str = DEFAULT_SCAMPER_BIN,
                 method: str = "udp-paris",
                 use_sudo: bool = True,
                 pace_ms: int = 40):
        self.scamper = scamper_bin
        self.method = method
        self.use_sudo = use_sudo
        self.pace_ms = pace_ms
        if not os.path.exists(self.scamper):
            raise FileNotFoundError(f"scamper binary not found at {self.scamper}")

    def _build_cmd(self, dest: str, ttl: int, attempts: int = 1, use_sudo: bool = False) -> str:
        # Build a scamper command that applies the trace template to the -i target list
        trace_tpl = f"trace -P {self.method} -q {attempts} -f {ttl} -m {ttl}"
        # Use -O json for direct JSON output; some installs require -o file, but prefer stdout.
        base = f"{shlex.quote(self.scamper)} -O json -i {shlex.quote(dest)} -c {shlex.quote(trace_tpl)}"
        if use_sudo:
            # -n avoids password prompt; ensure sudoers config if used in automation
            return f"sudo -n {base}"
        return base

    def _run_cmd(self, cmd: str) -> str:
        # Run command and return stdout. Caller handles exceptions.
        proc = subprocess.run(cmd, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return proc.stdout

    def _parse_scamper_json_v01(self, out: str, ttl: int) -> ProbeEvent:
        event: ProbeEvent = {
            "target": None, "ttl": ttl, "flow_id": 0, "protocol": self.method if hasattr(self, "method") else "udp-paris",
            "status": "timeout", "hop_ip": None, "rtt_ms": None,
            "timestamp": datetime.utcnow().isoformat(), "raw": {}
        }

        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            if obj.get("type") != "trace":
                continue

            # Keep raw for debugging
            event["raw"] = obj
            dst = obj.get("dst") or obj.get("target")
            event["target"] = dst

            # Find the reply for the TTL we just probed
            hops = obj.get("hops", []) or []
            for hop in hops:
                if hop.get("probe_ttl") != ttl:
                    continue

                ip = hop.get("addr")
                rtt = hop.get("rtt")
                itype = hop.get("icmp_type")
                icode = hop.get("icmp_code")

                status = "ttl_exceeded"  # default for intermediate routers

                # --- Destination classification by method ---
                # UDP-Paris: dest replies ICMP Dest Unreachable, Port Unreachable (3,3)
                if itype == 3 and icode == 3:
                    status = "dest_reached"

                # ICMP-Paris: dest Echo Reply (type 0)
                elif itype == 0:
                    status = "dest_reached"

                # Fallback: if reply IP equals destination, treat as dest even if ICMP fields are odd
                if ip and dst and ip == dst:
                    status = "dest_reached"

                event.update({"hop_ip": ip, "rtt_ms": rtt, "status": status})
                return event

            # If we saw the trace but not the specific TTL's reply, leave as timeout
            return event

        # No trace record found at all → leave as timeout with raw empty
        return event


    def probe_once(self, dest: str, ttl: int, flow_id: int = 0) -> ProbeEvent:
        # pacing with tiny jitter so quick loops don't overwhelm the network
        sleep_s = max(0, (self.pace_ms + random.randint(-10, 10)) / 1000.0)
        time.sleep(sleep_s)

        last_out: Optional[str] = None
        # Try without sudo first (if configured), then try with sudo if allowed by self.use_sudo
        tries = [False]
        if self.use_sudo:
            tries.append(True)

        for use_sudo in tries:
            cmd = self._build_cmd(dest, ttl, attempts=1, use_sudo=use_sudo)
            try:
                out = self._run_cmd(cmd)
            except Exception as e:
                last_out = f"exception: {e}"
                out = last_out
            last_out = out

            # quick failure checks
            if "could not chown /var/empty" in out.lower():
                # permission/privsep misconfiguration — return explicit error in raw
                return {
                    "target": dest,
                    "ttl": ttl,
                    "flow_id": flow_id,
                    "protocol": self.method,
                    "status": "timeout",
                    "hop_ip": None,
                    "rtt_ms": None,
                    "timestamp": datetime.utcnow().isoformat(),
                    "raw": {"error": "privsep: check /var/empty permissions", "output": out}
                }

            # scamper prints usage when mis-invoked; detect that and return error
            if out.strip().startswith("usage: scamper"):
                # include output for debugging
                return {
                    "target": dest,
                    "ttl": ttl,
                    "flow_id": flow_id,
                    "protocol": self.method,
                    "status": "timeout",
                    "hop_ip": None,
                    "rtt_ms": None,
                    "timestamp": datetime.utcnow().isoformat(),
                    "raw": {"error": "scamper usage", "output": out}
                }

            # Otherwise try parse; if parseable, return
            parsed = self._parse_scamper_json_v01(out, ttl)
            # If parsed contains some useful info (hop_ip or raw trace), return it
            if parsed.get("raw"):
                parsed["flow_id"] = flow_id
                parsed["protocol"] = self.method
                return parsed
            # else try next (sudo vs non-sudo)
        # nothing worked; return a timeout-ish event with last output
        return {
            "target": dest,
            "ttl": ttl,
            "flow_id": flow_id,
            "protocol": self.method,
            "status": "timeout",
            "hop_ip": None,
            "rtt_ms": None,
            "timestamp": datetime.utcnow().isoformat(),
            "raw": {"output": last_out}
        }
