"""
Configuration settings for the Slack Attendance Bot.
Contains all configurable parameters and environment variable access.
"""

import os

"""
Configuration settings for the Slack Attendance Bot.
"""
##SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
#SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
#AUDIT_CHANNEL_ID = os.environ.get("AUDIT_CHANNEL_ID")

SLACK_BOT_TOKEN = "xoxb-1301357252337-8564491585879-GreN9yQ6shnIAgQYEcIBhSbM"
SLACK_SIGNING_SECRET = "54ccf63ba614d01320be7a8a34b16474"
AUDIT_CHANNEL_ID = "C08E6PHE68H"

# Flask app settings
UPLOAD_FOLDER = "uploads"
PORT = 8000

# Constants for escalation timing
SUPERVISOR_ESCALATION_MINUTES = 2  # Time to wait before escalating to second supervisor
SUPERVISOR_NOTIFICATION_INTERVAL_MINUTES = 30  # Minimum time between supervisor notifications
SCHEDULER_CHECK_INTERVAL_MINUTES = 2  # How often to check for missed logins

# Database settings
DB_PATH = "logger.db"

# Logging configuration
LOG_FILE = "slackbot.log"
LOG_LEVEL = "INFO"
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'


# Add these lines to your existing config.py file

# Base URL for email acknowledgment links
BASE_URL = "https://be62-2406-b400-b9-d75c-60e3-62d-eee4-531a.ngrok-free.app"  # Update to your actual server address
#BASE_URL1 = "https://your-slackbot-app.azurewebsites.net"
# Email notification settings
EMAIL_NOTIFICATIONS_ENABLED = True  # Set to False to disable email notifications
USE_SUPERVISOR_EMAIL = True  # Whether to use supervisor's email for notifications

# Outlook settings - uncomment if you need custom settings
# OUTLOOK_PROFILE = "Default"  # Optional: specify Outlook profile name

# Email templates location
EMAIL_TEMPLATES_DIR = "templates/email"  # Optional: location for HTML email templates

