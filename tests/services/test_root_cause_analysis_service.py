import json

from tests.conftest import FakeResponse


class _CaptureSupabase:
    def __init__(self):
        self.updates = []

    def table(self, _name):
        return self

    def update(self, data):
        self._pending = dict(data)
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def execute(self):
        self.updates.append(self._pending)
        return FakeResponse([])


def test_root_cause_analysis_success_persists_reasoning_and_analyzed_status():
    from services.root_cause_analysis import run_root_cause_analysis

    capture = _CaptureSupabase()

    def analyze_fn(*, logs):
        assert "connection refused" in logs
        return {
            "root_cause": "Upstream dependency unreachable.",
            "recommended_actions": [
                "Check service Y health",
                "Verify DNS and network policy",
                "Rollback last deploy if needed",
            ],
            "urgency": "immediate",
        }

    ok = run_root_cause_analysis(
        "inc-rca-1",
        "error: connection refused to svc-y",
        supabase_client=capture,
        analyze_fn=analyze_fn,
    )

    assert ok is True
    assert len(capture.updates) == 1
    row = capture.updates[0]
    assert row["status"] == "analyzed"
    parsed = json.loads(row["agent_reasoning"])
    assert parsed["root_cause"] == "Upstream dependency unreachable."
    assert len(parsed["recommended_actions"]) >= 3
    assert parsed["urgency"] == "immediate"


def test_root_cause_analysis_failure_does_not_raise_and_skips_db():
    from services.root_cause_analysis import run_root_cause_analysis

    capture = _CaptureSupabase()

    def analyze_fn(*, logs):
        raise RuntimeError("LLM timeout")

    ok = run_root_cause_analysis(
        "inc-rca-2",
        "any logs",
        supabase_client=capture,
        analyze_fn=analyze_fn,
    )

    assert ok is False
    assert capture.updates == []


def test_root_cause_analysis_insufficient_actions_skips_persist():
    from services.root_cause_analysis import run_root_cause_analysis

    capture = _CaptureSupabase()

    def analyze_fn(*, logs):
        return {
            "root_cause": "Short",
            "recommended_actions": ["only one", "only two"],
            "urgency": "monitor",
        }

    ok = run_root_cause_analysis(
        "inc-rca-3",
        "sample logs",
        supabase_client=capture,
        analyze_fn=analyze_fn,
    )

    assert ok is False
    assert capture.updates == []
