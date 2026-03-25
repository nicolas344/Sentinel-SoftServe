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


def test_auto_classification_success_persists_valid_label():
    from services.incident_classification import apply_auto_classification

    capture = _CaptureSupabase()

    def classify_fn(**_kwargs):
        return "oom"

    result = apply_auto_classification(
        "inc-1",
        "Worker died",
        "high",
        "OOMKilled",
        supabase_client=capture,
        classify_fn=classify_fn,
    )

    assert result == "oom"
    assert capture.updates == [
        {"status": "investigating"},
        {"incident_type": "oom"},
    ]


def test_auto_classification_sets_investigating_before_llm_runs():
    from services.incident_classification import apply_auto_classification

    capture = _CaptureSupabase()

    def classify_fn(**_kwargs):
        assert capture.updates == [{"status": "investigating"}]
        return "app_crash"

    out = apply_auto_classification(
        "inc-2",
        "Segfault",
        "critical",
        "stack trace...",
        supabase_client=capture,
        classify_fn=classify_fn,
    )

    assert out == "app_crash"
    assert capture.updates[-1] == {"incident_type": "app_crash"}


def test_auto_classification_llm_error_persists_unknown():
    from services.incident_classification import apply_auto_classification

    capture = _CaptureSupabase()

    def classify_fn(**_kwargs):
        raise RuntimeError("LLM unavailable")

    result = apply_auto_classification(
        "inc-3",
        "Mystery",
        "medium",
        None,
        supabase_client=capture,
        classify_fn=classify_fn,
    )

    assert result == "unknown"
    assert capture.updates[0] == {"status": "investigating"}
    assert capture.updates[1] == {"incident_type": "unknown"}
