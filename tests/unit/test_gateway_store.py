import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from integrations.gateway.settings import AdmissionLimits
from integrations.gateway.store import AdmissionDenied, QuotaStore
from voiceagent.settings import PROJECT_ROOT


def test_persistent_shared_store_blocks_concurrent_instances_and_restart(tmp_path):
    path = tmp_path / "limits.sqlite3"
    limits = AdmissionLimits()
    QuotaStore(path, limits)

    def admit(_):
        try:
            return QuotaStore(path, limits).reserve("same-principal", "same-network", 100)
        except AdmissionDenied:
            return None

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(admit, range(20)))
    assert len([result for result in results if result]) == 1
    # A fresh interpreter cannot reset quotas/concurrency by making a new store instance.
    program = (
        "import sys; from pathlib import Path; "
        "from integrations.gateway.store import QuotaStore, AdmissionDenied; "
        "from integrations.gateway.settings import AdmissionLimits; "
        "store=QuotaStore(Path(sys.argv[1]),AdmissionLimits()); "
        "store.reserve('same-principal','same-network',200)"
    )
    child = subprocess.run(
        [sys.executable, "-c", program, str(path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        timeout=30,
    )
    assert child.returncode != 0 and b"AdmissionDenied" in child.stderr


@pytest.mark.parametrize("dimension", ["global", "principal", "network"])
def test_daily_seconds_reserve_worker_maximum_and_never_refund_on_end(tmp_path, dimension):
    limits = replace(AdmissionLimits(), **{f"{dimension}_daily_seconds": 1800})
    store = QuotaStore(tmp_path / "limits.sqlite3", limits)
    first = store.reserve("user", "network", 100)
    store.cleaned(first.id)
    with pytest.raises(AdmissionDenied):
        store.reserve("user", "network", 200)
    assert store.reserve("user", "network", 86400 + 100)


def test_global_budget_cannot_be_bypassed_with_new_user_network_and_session(tmp_path):
    store = QuotaStore(
        tmp_path / "limits.sqlite3", replace(AdmissionLimits(), global_daily_sessions=1)
    )
    first = store.reserve("first", "first", 100)
    store.cleaned(first.id)
    with pytest.raises(AdmissionDenied):
        store.reserve("different", "different", 200)


def test_expired_or_failed_cleanup_never_frees_capacity(tmp_path):
    store = QuotaStore(tmp_path / "limits.sqlite3", AdmissionLimits())
    first = store.reserve("user", "net", 100)
    for now in range(1000, 1400, 60):
        store.claim_cleanup(first.id, now)
        store.cleanup_failed(first.id, now)
    assert store.get(first.id).attempts == 6
    assert not store.due(5000)
    with pytest.raises(AdmissionDenied):
        store.reserve("user", "net", 5000)


def test_minute_limit_survives_closed_sessions_and_clock_window(tmp_path):
    limits = replace(AdmissionLimits(), principal_per_minute=1)
    store = QuotaStore(tmp_path / "limits.sqlite3", limits)
    first = store.reserve("user", "net", 100)
    store.cleaned(first.id)
    with pytest.raises(AdmissionDenied):
        store.reserve("user", "net", 101)
    assert store.reserve("user", "net", 161)


@pytest.mark.parametrize(
    "values", [{"token_seconds": 600}, {"session_seconds": 2000}, {"global_concurrent": False}]
)
def test_limits_are_validated(values):
    with pytest.raises(ValueError):
        replace(AdmissionLimits(), **values)
