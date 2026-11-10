import pytest


@pytest.fixture
def ts():
    import superviseme.utils.task_scheduler as mod
    return mod


JOBS = [
    ("_reminders_job", "superviseme.utils.reminders", "run_reminders"),
    ("_retention_job", "superviseme.utils.privacy", "purge_expired"),
    ("_weekly_reports_job", "superviseme.utils.weekly_notifications", "send_all_weekly_supervisor_reports"),
]


@pytest.mark.parametrize("job,module,func", JOBS)
def test_job_is_a_noop_without_app(ts, monkeypatch, job, module, func):
    monkeypatch.setattr(ts, "_flask_app", None)
    called = []
    import importlib
    monkeypatch.setattr(importlib.import_module(module), func, lambda *a, **k: called.append(1))
    getattr(ts, job)()
    assert called == []


@pytest.mark.parametrize("job,module,func", JOBS)
def test_job_runs_target_inside_app_context(ts, app, monkeypatch, job, module, func):
    import importlib
    monkeypatch.setenv("RETENTION_ENABLED", "true")
    from flask import has_app_context
    seen = []
    monkeypatch.setattr(ts, "_flask_app", app)
    monkeypatch.setattr(importlib.import_module(module), func, lambda *a, **k: seen.append(has_app_context()) or {})
    getattr(ts, job)()
    assert seen == [True]


@pytest.mark.parametrize("job,module,func", JOBS)
def test_job_swallows_errors(ts, app, monkeypatch, job, module, func):
    import importlib
    monkeypatch.setenv("RETENTION_ENABLED", "true")

    def boom(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(ts, "_flask_app", app)
    monkeypatch.setattr(importlib.import_module(module), func, boom)
    getattr(ts, job)()  # must not raise: a failing job must never kill the scheduler thread


def test_init_scheduler_registers_expected_jobs_once(ts, app, monkeypatch):
    class FakeScheduler:
        instances = []

        def __init__(self, *a, **k):
            self.jobs, self.running = {}, False
            FakeScheduler.instances.append(self)

        def add_job(self, func, trigger, id, **kw):
            self.jobs[id] = (func, str(trigger))

        def start(self):
            self.running = True

        def get_jobs(self):
            return [type("J", (), {"id": i, "name": i, "next_run_time": None, "trigger": "t"}) for i in self.jobs]

    monkeypatch.setattr(ts, "BackgroundScheduler", FakeScheduler)
    monkeypatch.setattr(ts, "scheduler", None)
    monkeypatch.setattr(ts.atexit, "register", lambda *a, **k: None)
    ts.init_scheduler(app)
    ts.init_scheduler(app)  # second call is ignored
    assert len(FakeScheduler.instances) == 1
    sched = FakeScheduler.instances[0]
    assert set(sched.jobs) == {"weekly_supervisor_reports", "daily_reminders", "retention_purge"}
    assert "day_of_week='mon'" in sched.jobs["weekly_supervisor_reports"][1]
    assert all(f.startswith("superviseme.utils.task_scheduler:") for f, _ in sched.jobs.values())
    status = ts.get_scheduler_status()
    assert status["status"] == "running" and len(status["jobs"]) == 3
    monkeypatch.setattr(ts.scheduler, "running", False)
    assert ts.get_scheduler_status()["status"] == "stopped"


def test_status_when_not_initialised(ts, monkeypatch):
    monkeypatch.setattr(ts, "scheduler", None)
    assert ts.get_scheduler_status() == {"status": "not_initialized", "jobs": []}


def test_retention_is_off_by_default(ts, app, monkeypatch, admin_user):
    import importlib
    from superviseme.utils import privacy
    monkeypatch.delenv("RETENTION_ENABLED", raising=False)
    monkeypatch.setattr(ts, "_flask_app", app)
    called = []
    monkeypatch.setattr(privacy, "purge_expired", lambda *a, **k: called.append(1) or {})
    ts._retention_job()
    assert called == []
    with app.app_context():
        assert privacy.retention_enabled() is False
    monkeypatch.setenv("RETENTION_ENABLED", "true")
    ts._retention_job()
    assert called == [1]
    importlib.import_module("superviseme.utils.privacy")
