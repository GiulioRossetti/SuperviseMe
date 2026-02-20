"""
Task scheduler service for SuperviseMe application
Handles background tasks like weekly email notifications
"""
import atexit
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from superviseme.utils.weekly_notifications import send_all_weekly_supervisor_reports

logger = logging.getLogger(__name__)

scheduler = None


def init_scheduler(app):
    """
    Initialize the background scheduler with the Flask app context
    
    Args:
        app: Flask application instance
    """
    global scheduler
    
    if scheduler is None:
        scheduler = BackgroundScheduler(daemon=True)
        
        # Schedule weekly supervisor reports to run every Monday at 9:00 AM
        scheduler.add_job(
            func=scheduled_weekly_reports,
            trigger=CronTrigger(day_of_week='mon', hour=9, minute=0),
            id='weekly_supervisor_reports',
            name='Send weekly supervisor reports',
            replace_existing=True
        )
        
        # Store app context for use in scheduled jobs
        scheduler._app_context = app
        
        try:
            scheduler.start()
            logger.info("Background scheduler started successfully")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {str(e)}")
        
        # Shut down the scheduler when exiting the app
        atexit.register(lambda: shutdown_scheduler())


def scheduled_weekly_reports():
    """
    Scheduled job to send weekly supervisor reports
    This runs every Monday morning at 9:00 AM
    """
    if scheduler and hasattr(scheduler, '_app_context'):
        with scheduler._app_context.app_context():
            try:
                logger.info("Starting scheduled weekly supervisor reports")
                results = send_all_weekly_supervisor_reports()
                logger.info(f"Weekly reports completed: {results}")
            except Exception as e:
                logger.error(f"Error in scheduled weekly reports: {str(e)}")
    else:
        logger.error("App context not available for scheduled job")


def shutdown_scheduler():
    """
    Shutdown the background scheduler
    """
    global scheduler
    if scheduler:
        scheduler.shutdown()
        logger.info("Background scheduler shut down")


def trigger_weekly_reports_now():
    """
    Manually trigger weekly reports (useful for testing and admin purposes)
    
    Returns:
        dict: Results of the email sending process
    """
    try:
        logger.info("Manually triggering weekly supervisor reports")
        results = send_all_weekly_supervisor_reports()
        logger.info(f"Manual weekly reports completed: {results}")
        return results
    except Exception as e:
        logger.error(f"Error in manual weekly reports: {str(e)}")
        return {'error': str(e)}


def get_scheduler_status():
    """
    Get the current status of the scheduler and its jobs
    
    Returns:
        dict: Scheduler status information
    """
    if scheduler is None:
        return {'status': 'not_initialized', 'jobs': []}
    
    if not scheduler.running:
        return {'status': 'stopped', 'jobs': []}
    
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            'id': job.id,
            'name': job.name,
            'next_run_time': str(job.next_run_time) if job.next_run_time else None,
            'trigger': str(job.trigger)
        })
    
    return {
        'status': 'running',
        'jobs': jobs
    }


def reschedule_weekly_reports(day_of_week='mon', hour=9, minute=0):
    """
    Reschedule the weekly reports to a different time
    
    Args:
        day_of_week (str): Day of the week ('mon', 'tue', etc.)
        hour (int): Hour in 24-hour format (0-23)
        minute (int): Minute (0-59)
    
    Returns:
        bool: True if rescheduled successfully, False otherwise
    """
    global scheduler
    if scheduler is None:
        logger.error("Scheduler not initialized")
        return False
    
    try:
        # Remove existing job
        scheduler.remove_job('weekly_supervisor_reports')
        
        # Add new job with new schedule
        scheduler.add_job(
            func=scheduled_weekly_reports,
            trigger=CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute),
            id='weekly_supervisor_reports',
            name='Send weekly supervisor reports',
            replace_existing=True
        )
        
        logger.info(f"Weekly reports rescheduled to {day_of_week} at {hour:02d}:{minute:02d}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to reschedule weekly reports: {str(e)}")
        return False