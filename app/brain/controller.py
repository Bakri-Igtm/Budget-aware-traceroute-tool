# app/brain/controller.py
import time
from app.brain.state import RunState
from app.brain.rules import confident_rule, dark_rule, should_stop_run
from typing import Optional

class BudgetController:
    """
    Minimal budget-aware controller.
    prober must implement probe_once(dest, ttl, flow_id) -> ProbeEvent (dict)
    settings is a simple namespace or dataclass with attributes:
      max_ttl, per_hop_budget, repeats_needed, total_budget, flow_ids (tuple), per_probe_delay_s (float)
    """
    def __init__(self, prober, settings):
        self.prober = prober
        self.s = settings

    def run(self, dest: str):
        run = RunState(max_ttl=self.s.max_ttl, total_budget=self.s.total_budget)
        flow_ids = list(self.s.flow_ids) if getattr(self.s, "flow_ids", None) else [0]

        while not should_stop_run(run):
            ttl = run.ttl
            if ttl > run.max_ttl:
                break
            tstate = run.per_ttl[ttl]

            # If this TTL already decided, move on
            if tstate.final is not None or tstate.confident:
                run.ttl += 1
                continue

            # Choose a flow id round-robin (small peek to detect ECMP, can be static)
            chosen_flow = flow_ids[(tstate.attempts) % len(flow_ids)]

            # Send one probe
            ev = self.prober.probe_once(dest, ttl, flow_id=chosen_flow)
            run.probes_used += 1
            tstate.attempts += 1

            # Interpret event (ev should be the ProbeEvent dict)
            status = ev.get("status")
            hop_ip = ev.get("hop_ip")

            # --- Hard stop if we see the destination IP (robust guard) ---
            if hop_ip and hop_ip == dest:
                tstate.counts[hop_ip] += 1
                tstate.final = hop_ip
                tstate.confident = True
                run.dest_reached = True
                run.stop_reason = "dest_reached"
                break


            if status in ("ttl_exceeded", "dest_reached") and hop_ip:
                tstate.counts[hop_ip] += 1
                # If destination style reply -> mark dest and stop later
                if status == "dest_reached":
                    tstate.final = hop_ip
                    tstate.confident = True
                    run.dest_reached = True
                    run.stop_reason = "dest_reached"
                    break
            else:
                # treat as timeout/unreach: increment timeouts
                tstate.timeouts += 1

            # Check per-hop decisions:
            if confident_rule(tstate.counts, self.s.repeats_needed):
                # pick the top IP as final
                top_ip = max(tstate.counts, key=lambda k: tstate.counts[k])
                tstate.final = top_ip
                tstate.confident = True
            elif dark_rule(tstate.timeouts, tstate.attempts, self.s.per_hop_budget):
                tstate.final = "∅"  # dark hop

            # Move on if decided or budget used up for this hop
            if tstate.final is not None or tstate.attempts >= self.s.per_hop_budget:
                run.ttl += 1
            else:
                # optionally small pause between probes to same hop
                time.sleep(getattr(self.s, "per_probe_delay_s", 0.03))

        # Build summary result
        # Build summary result
        path = {}
        for k in range(1, run.max_ttl + 1):
            final = run.per_ttl[k].final
            if final is None:
                continue
            path[k] = final
            if final == dest:
                break


        summary = {
            "target": dest,
            "path": path,
            "probes_used": run.probes_used,
            "stop_reason": run.stop_reason or ("max_ttl" if run.ttl > run.max_ttl else "unknown"),
            "per_ttl": {k: {
                "final": run.per_ttl[k].final,
                "counts": dict(run.per_ttl[k].counts),
                "timeouts": run.per_ttl[k].timeouts,
                "attempts": run.per_ttl[k].attempts
            } for k in range(1, run.max_ttl + 1)}
        }
        return summary
