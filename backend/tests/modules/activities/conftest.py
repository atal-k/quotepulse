import pytest

from app.modules.activities import service as activities_service


@pytest.fixture(autouse=True)
def stub_enqueue(monkeypatch: pytest.MonkeyPatch) -> list:
    """Activity creation in this module's tests must not touch the real job queue (Phase 2B
    wires a real Redis). Records calls so tests can assert enqueue happened with the right id."""
    calls: list = []
    monkeypatch.setattr(
        activities_service,
        "enqueue_process_activity",
        lambda activity_id: calls.append(activity_id),
    )
    return calls
