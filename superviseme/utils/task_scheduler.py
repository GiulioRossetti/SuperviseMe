"""
superviseme/utils/task_scheduler.py
-------------------------------------
Background scheduler for SuperviseMe.

Changes from original
---------------------
* Uses APScheduler SQLAlchemyJobStore so that jobs survive process restarts
  and are not duplicated when multiple Gunicorn workers start (only one
  worker should have ENABLE_SCHEDULER=true; the job store handles the rest).
* coalesce=True + max_instances=1 prevent pile-up if a job takes longer than
  its interval.
* replace_existing=True means re-deploying does not create duplicate job rows.

Stage 7 fix
-----------
APScheduler SQLAlchemyJobStore serialises jobs with pickle.  Pickle resolves
callables by their module-qualified name, so local closures (functions defined
*inside* another function) cannot be pickled — they have no stable import
path.  All job callables are now defined at module level and reference the
Flask app via the module-level ``_flask_app`` variable set by ``init_scheduler``.
"""
import atexit
import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler: BackgroundScheduler | None = None

# Module-level app reference — set by init_scheduler() so that module-level
# job functions can push an app context without relying on closures.
_flask_app = None


def _retention_job():
    """Nightly application of the data retention policy."""
    app = _flask_app
    if app is None:
        return
    with app.app_context():
        try:
            from superviseme.utils.privacy import purge_expired
            logger.info("APScheduler: retention purge: %s", purge_expired())
        except Exception as exc:
            logger.error("APScheduler: retention purge failed: %s", exc, exc_info=True)


# ---------------------------------------------------------------------------
# Job functions (must be at module level for APScheduler pickle serialisation)
# ---------------------------------------------------------------------------

def _weekly_reports_job():
    """Send weekly supervisor summary reports.

    Referenced as "superviseme.utils.task_scheduler:_weekly_reports_job" by
    APScheduler — the module-level definition makes it picklable.
    """
    app = _flask_app
    if app is None:
        logger.error("APScheduler: _flask_app not set; skipping weekly reports job")
        return
    with app.app_context():
        try:
            logger.info("APScheduler: running weekly supervisor reports")
            from superviseme.utils.weekly_notifications import send_all_weekly_supervisor_reports
            results = send_all_weekly_supervisor_reports()
            logger.info("APScheduler: weekly reports done: %s", results)
        except Exception as exc:
            logger.error("APScheduler: weekly reports failed: %s", exc, exc_info=True)


def _reminders_job():
    """Daily automatic reminders (tasks, milestones, inactive students, meetings)."""
    app = _flask_app
    if app is None:
        logger.error("APScheduler: _flask_app not set; skipping reminders job")
        return
    with app.app_context():
        try:
            from superviseme.utils.reminders import run_reminders
            logger.info("APScheduler: reminders done: %s", run_reminders())
        except Exception as exc:
            logger.error("APScheduler: reminders failed: %s", exc, exc_info=True)


# ---------------------------------------------------------------------------
# Scheduler lifecycle
# ---------------------------------------------------------------------------

def init_scheduler(app):
    """Initialise the background scheduler.

    Should be called once per process — the ENABLE_SCHEDULER env var in
    __init__.py already guards against multi-worker duplication at the
    process level.  The SQLAlchemyJobStore additionally prevents duplicate
    job rows in the database.
    """
    global scheduler, _flask_app

    if scheduler is not None:
        logger.warning("init_scheduler called more than once; skipping second init")
        return

    # Store the app reference so module-level job functions can use it
    _flask_app = app

    # --- Job store configuration ----------------------------------------
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    job_defaults = {
        "coalesce": True,       # merge missed executions into one
        "max_instances": 1,     # never run the same job in parallel
    }

    jobstores: dict = {}
    try:
        from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
        jobstores["default"] = SQLAlchemyJobStore(url=db_uri)
        logger.info(
            "APScheduler using SQLAlchemyJobStore (%s)",
            db_uri.split("@")[-1] if "@" in db_uri else db_uri[:60],
        )
    except Exception as exc:
        logger.warning(
            "SQLAlchemyJobStore unavailable (%s); falling back to in-memory MemoryJobStore. "
            "Jobs will NOT survive process restarts.",
            exc,
        )

    # --- Scheduler creation ---------------------------------------------
    scheduler = BackgroundScheduler(
        jobstores=jobstores or None,
        job_defaults=job_defaults,
        daemon=True,
    )

    # --- Job registration -----------------------------------------------
    # Reference the job function by its fully-qualified module path so APScheduler
    # can resolve it via import at deserialisation time (required for SQLAlchemyJobStore).
    scheduler.add_job(
        func="superviseme.utils.task_scheduler:_weekly_reports_job",
        trigger=CronTrigger(day_of_week="mon", hour=9, minute=0),
        id="weekly_supervisor_reports",
        name="Send weekly supervisor reports",
        replace_existing=True,
    )

    scheduler.add_job(
        func="superviseme.utils.task_scheduler:_reminders_job",
        trigger=CronTrigger(hour=8, minute=0),
        id="daily_reminders",
        name="Send automatic reminders",
        replace_existing=True,
    )

    scheduler.add_job(
        func="superviseme.utils.task_scheduler:_retention_job",
        trigger=CronTrigger(hour=3, minute=30),
        id="retention_purge",
        name="Apply data retention policy",
        replace_existing=True,
    )

    # --- Start ----------------------------------------------------------
    try:
        scheduler.start()
        logger.info("APScheduler started (jobs: %s)", [j.id for j in scheduler.get_jobs()])
    except Exception as exc:
        logger.error("APScheduler failed to start: %s", exc, exc_info=True)

    atexit.register(shutdown_scheduler)


def shutdown_scheduler():
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler shut down")


def trigger_weekly_reports_now():
    """Manually trigger weekly reports (admin / testing)."""
    try:
        results = _weekly_reports_job()
        logger.info("Manual weekly reports: %s", results)
        return results
    except Exception as exc:
        logger.error("Manual weekly reports error: %s", exc, exc_info=True)
        return {"error": str(exc)}


def get_scheduler_status() -> dict:
    """Return current scheduler status (for admin dashboard)."""
    if scheduler is None:
        return {"status": "not_initialized", "jobs": []}
    if not scheduler.running:
        return {"status": "stopped", "jobs": []}

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": str(job.next_run_time) if job.next_run_time else None,
            "trigger": str(job.trigger),
        })
    return {"status": "running", "jobs": jobs}


def reschedule_weekly_reports(day_of_week: str = "mon", hour: int = 9, minute: int = 0) -> bool:
    """Change the schedule of the weekly reports job."""
    if scheduler is None:
        logger.error("reschedule_weekly_reports: scheduler not initialised")
        return False
    try:
        scheduler.reschedule_job(
            "weekly_supervisor_reports",
            trigger=CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute),
        )
        logger.info("Weekly reports rescheduled to %s %02d:%02d", day_of_week, hour, minute)
        return True
    except Exception as exc:
        logger.error("reschedule_weekly_reports failed: %s", exc, exc_info=True)
        return False
