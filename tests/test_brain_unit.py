# tests/test_brain_unit.py
import pytest

from app.brain.controller import BudgetController
from app.config import Settings
from app.prober.fake import FakeProber


def test_budgetcontroller_initialization():
    """Test that BudgetController initializes correctly with FakeProber and Settings."""
    s = Settings(total_budget=10, per_hop_budget=3, repeats_needed=2)
    fake = FakeProber(script={})
    ctrl = BudgetController(fake, s)
    assert ctrl.settings.total_budget == 10
    assert ctrl.settings.per_hop_budget == 3
    assert ctrl.settings.repeats_needed == 2


def test_budgetcontroller_run_fake():
    """Test BudgetController run() method using FakeProber and fake traceroute script."""
    # Build fake probe script like tools/run_budget.py
    script = {}
    for ttl in range(1, 4):
        script[(ttl, 0)] = [{
            "target": "8.8.8.8",
            "ttl": ttl,
            "flow_id": 0,
            "protocol": "udp-paris",
            "status": "ttl_exceeded",
            "hop_ip": f"10.0.0.{ttl}",
            "rtt_ms": 10.0 + ttl,
            "timestamp": None,
            "raw": {}
        }]
    script[(4, 0)] = [{
        "target": "8.8.8.8",
        "ttl": 4,
        "flow_id": 0,
        "protocol": "udp-paris",
        "status": "dest_reached",
        "hop_ip": "8.8.8.8",
        "rtt_ms": 30.0,
        "timestamp": None,
        "raw": {}
    }]

    fake = FakeProber(script=script)
    s = Settings(total_budget=20, per_hop_budget=5, repeats_needed=1)
    ctrl = BudgetController(fake, s)

    result = ctrl.run("8.8.8.8")

    # The result should include a key like "path" or "hops"
    assert isinstance(result, dict)
    assert any(k in result for k in ("path", "hops", "trace")), "Expected traceroute result keys"
    assert "8.8.8.8" in str(result), "Expected target in result output"


def test_budgetcontroller_budget_exceeded():
    """Ensure the controller respects the total budget."""
    s = Settings(total_budget=1, per_hop_budget=1)
    fake = FakeProber(script={})
    ctrl = BudgetController(fake, s)
    # Try to run more than the allowed total budget
    ctrl.remaining_budget = 0
    with pytest.raises(Exception):
        ctrl.run("8.8.8.8")
