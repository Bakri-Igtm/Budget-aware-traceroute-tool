# app/brain/controller.py

import time
from typing import Optional

from app.brain.state import RunState
from app.brain.rules import confident_rule, dark_rule, uncertain


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

            # If this TTL is already decided, just move on.
            if tstate.final is not None or tstate.confident:
                run.ttl += 1
                continue

            # -------------------------------
            # 1) Compute dynamic per-hop cap
            # -------------------------------
            base_cap = self.s.per_hop_budget
            dyn_cap = base_cap  # start with base

            # Look at previous hop to detect "trouble zone"
            prev = run.per_ttl.get(ttl - 1) if ttl > 1 else None

            allow_rollover = False
            # Only even consider spending extra credits if this hop is genuinely uncertain
            if uncertain(tstate):
                # Only try extra probes deeper in the path (beyond edge),
                # and when the previous hop was dark or noisy.
                if ttl > 6 and prev is not None:
                    prev_noisy = (prev.final == "∅") or (prev.timeouts >= 2)
                    if prev_noisy:
                        allow_rollover = True

            if allow_rollover:
                extra_allow = min(
                    run.pool,
                    getattr(self.s, "rollover_cap_per_hop", 0)
                )
                dyn_cap = base_cap + extra_allow
                dyn_cap = min(
                    dyn_cap,
                    getattr(self.s, "hard_per_hop_max", base_cap),
                )

            # Store for debugging / reporting
            tstate.base_cap = base_cap
            tstate.dyn_cap = dyn_cap

            # -------------------------------
            # 2) Choose flow & guard budget
            # -------------------------------
            # tiny ECMP peek via round-robin flow IDs
            chosen_flow = flow_ids[(tstate.attempts) % len(flow_ids)]

            if run.probes_used >= run.total_budget:
                run.stop_reason = "budget_exhausted"
                break

            # -------------------------------
            # 3) Send one probe
            # -------------------------------
            ev = self.prober.probe_once(dest, ttl, flow_id=chosen_flow)
            run.probes_used += 1
            tstate.attempts += 1

            status = ev.get("status")
            hop_ip = ev.get("hop_ip")

            if status in ("ttl_exceeded", "dest_reached") and hop_ip:
                tstate.counts[hop_ip] += 1

                # If we get a destination-style reply, stop the entire run.
                if status == "dest_reached" or hop_ip == dest:
                    tstate.final = hop_ip
                    tstate.confident = True
                    run.dest_reached = True
                    run.stop_reason = "dest_reached"
                    break
            else:
                # timeout/unreach etc.
                tstate.timeouts += 1

            # -------------------------------
            # 4) Per-hop decision logic
            # -------------------------------
            if confident_rule(tstate.counts, self.s.repeats_needed):
                # The most frequent IP wins
                top_ip = max(tstate.counts, key=lambda k: tstate.counts[k])
                tstate.final = top_ip
                tstate.confident = True
            elif dark_rule(tstate.timeouts, tstate.attempts, dyn_cap):
                # Too much silence -> mark as dark
                tstate.final = "∅"

            # -------------------------------
            # 5) Move on or keep probing
            # -------------------------------
            if tstate.final is not None or tstate.attempts >= dyn_cap:
                used = tstate.attempts

                # If we used fewer probes than base_cap, deposit credits into the pool.
                if used < base_cap:
                    deposit = base_cap - used
                    run.pool = min(
                        run.pool + deposit,
                        getattr(self.s, "rollover_pool_max", 10),
                    )
                    tstate.pool_in = deposit
                else:
                    # If we went beyond base_cap, withdraw the extra from the pool.
                    extra_used = max(0, used - base_cap)
                    if extra_used > 0:
                        run.pool = max(0, run.pool - extra_used)
                        tstate.pool_out = extra_used

                run.ttl += 1
            else:
                # Still undecided and under dyn_cap -> keep probing this hop
                time.sleep(getattr(self.s, "per_probe_delay_s", 0.03))

        # -------------------------------
        # 6) Build summary result
        # -------------------------------
        path = {}
        for k in range(1, run.max_ttl + 1):
            if run.per_ttl[k].final is not None:
                path[k] = run.per_ttl[k].final

        return {
            "target": dest,
            "path": path,
            "probes_used": run.probes_used,
            "stop_reason": (
                run.stop_reason
                or ("max_ttl" if run.ttl > run.max_ttl else "unknown")
            ),
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
                }
                for k in range(1, run.max_ttl + 1)
            },
            "pool_remaining": run.pool,
        }
