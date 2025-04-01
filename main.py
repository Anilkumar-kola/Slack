"""
Main entry point for the Slack Attendance Bot.

This bot tracks employee attendance and sends notifications for missed check-ins
with an escalation workflow to supervisors when needed.
"""
import schedule  # type: ignore
import logging
import threading
import time
import config
import database
import notification_service
from app import app
import routes  # Import routes to register them with Flask

logger = logging.getLogger(__name__)

def scheduler_loop():
    """
    Start the scheduler loop to run periodic tasks.
    Runs in a separate thread.
    """
    logger.info("Starting scheduler loop")
    
    # Schedule the missed logins check
    schedule.every(config.SCHEDULER_CHECK_INTERVAL_MINUTES).minutes.do(
        notification_service.check_missed_logins
    )
    
    # Run the scheduler loop
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute


def main():
    """
    Main function to start the bot.
    Initialize the database, start the scheduler, and run the Flask app.
    """
    # Initialize the database
    database.init_database()
    
    # Start the scheduler thread
    scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
    scheduler_thread.start()
    logger.info("Scheduler thread started")
    
    # Run the Flask app
    logger.info(f"Starting Flask app on port {config.PORT}")
    app.run(host="0.0.0.0", port=config.PORT, debug=False)


if __name__ == "__main__":
    main()