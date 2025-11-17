# app/brain/controller.py
import time
from app.brain.state import RunState
from app.brain.rules import confident_rule, dark_rule, uncertain
from typing import Optional

class BudgetController:
    def __init__(self, prober, settings):
        self.prober = prober
        self.s = settings

    def run(self, dest: str):
        run = RunState(max_ttl=self.s.max_ttl, total_budget=self.s.total_budget)
        flow_ids = list(self.s.flow_ids) if getattr(self.s, "flow_ids", None) else [0]

        while run.probes_used < run.total_budget and run.ttl <= run.max_ttl:
            ttl = run.ttl
            tstate = run.per_ttl[ttl]

            # already decided? advance
            if tstate.final is not None or tstate.confident:
                run.ttl += 1
                continue

            # --- compute dynamic cap with rollover credits ---
            base_cap = self.s.per_hop_budget
            extra_allow = min(run.pool, getattr(self.s, "rollover_cap_per_hop", 0))
            dyn_cap = base_cap + extra_allow
            dyn_cap = min(dyn_cap, getattr(self.s, "hard_per_hop_max", base_cap))

            # only spend extras if this hop is uncertain
            if not uncertain(tstate):
                dyn_cap = base_cap

            tstate.base_cap = base_cap
            tstate.dyn_cap = dyn_cap

            # choose a flow id (round-robin over a tiny set)
            chosen_flow = flow_ids[(tstate.attempts) % len(flow_ids)]

            # guard global budget
            if run.probes_used >= run.total_budget:
                run.stop_reason = "budget_exhausted"
                break

            # --- send one probe ---
            ev = self.prober.probe_once(dest, ttl, flow_id=chosen_flow)
            run.probes_used += 1
            tstate.attempts += 1

            status = ev.get("status")
            hop_ip = ev.get("hop_ip")

            if status in ("ttl_exceeded", "dest_reached") and hop_ip:
                tstate.counts[hop_ip] += 1
                if status == "dest_reached" or hop_ip == dest:
                    # destination confirmed: lock and stop run
                    tstate.final = hop_ip
                    tstate.confident = True
                    run.dest_reached = True
                    run.stop_reason = "dest_reached"
                    break
            else:
                tstate.timeouts += 1

            # per-hop decisioning
            if confident_rule(tstate.counts, self.s.repeats_needed):
                top_ip = max(tstate.counts, key=lambda k: tstate.counts[k])
                tstate.final = top_ip
                tstate.confident = True
            elif dark_rule(tstate.timeouts, tstate.attempts, dyn_cap):
                tstate.final = "∅"

            # move on if decided or hit cap
            if tstate.final is not None or tstate.attempts >= dyn_cap:
                used = tstate.attempts

                # deposit if we used less than base
                if used < base_cap:
                    deposit = base_cap - used
                    run.pool = min(run.pool + deposit,
                                   getattr(self.s, "rollover_pool_max", 10))
                    tstate.pool_in = deposit
                else:
                    # withdraw extras from pool if used > base
                    extra_used = max(0, used - base_cap)
                    if extra_used > 0:
                        run.pool = max(0, run.pool - extra_used)
                        tstate.pool_out = extra_used

                run.ttl += 1
            else:
                time.sleep(getattr(self.s, "per_probe_delay_s", 0.03))

        # summary
        path = {}
        for k in range(1, run.max_ttl + 1):
            if run.per_ttl[k].final is not None:
                path[k] = run.per_ttl[k].final

        return {
            "target": dest,
            "path": path,
            "probes_used": run.probes_used,
            "stop_reason": run.stop_reason or ("max_ttl" if run.ttl > run.max_ttl else "unknown"),
            "per_ttl": {
                k: {
                    "final": run.per_ttl[k].final,
                    "counts": dict(run.per_ttl[k].counts),
                    "timeouts": run.per_ttl[k].timeouts,
                    "attempts": run.per_ttl[k].attempts,
                    # debug meta
                    "base_cap": run.per_ttl[k].base_cap,
                    "dyn_cap": run.per_ttl[k].dyn_cap,
                    "pool_in": run.per_ttl[k].pool_in,
                    "pool_out": run.per_ttl[k].pool_out,
                } for k in range(1, run.max_ttl + 1)
            },
            # optional: show remaining pool
            "pool_remaining": run.pool,
        }
