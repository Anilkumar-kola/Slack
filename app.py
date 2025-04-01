"""
Flask application setup for the Slack Attendance Bot.
Initializes the Flask app and Slack event adapter.
"""

import os
import logging

from flask import Flask
from slackeventsapi import SlackEventAdapter

import config
import slack_client

# Verify configuration immediately
if not config.SLACK_SIGNING_SECRET:
    raise ValueError("SLACK_SIGNING_SECRET is not set in config.py or environment variables")
    
if not config.SLACK_BOT_TOKEN:
    raise ValueError("SLACK_BOT_TOKEN is not set in config.py or environment variables")

print(f"CONFIG CHECK: SLACK_SIGNING_SECRET is {'SET' if config.SLACK_SIGNING_SECRET else 'NOT SET'}")
print(f"CONFIG CHECK: SLACK_BOT_TOKEN is {'SET' if config.SLACK_BOT_TOKEN else 'NOT SET'}")


import os
print(f"SLACK_SIGNING_SECRET value: '{os.environ.get('SLACK_SIGNING_SECRET')}'")
print(f"Looking for config in: {os.path.abspath('config.py')}")

import config
print(f"Loaded config has SLACK_SIGNING_SECRET: '{getattr(config, 'SLACK_SIGNING_SECRET', 'NOT FOUND')}'")

# Add these lines to your existing config.py file

# Base URL for email acknowledgment links
BASE_URL = "http://your-server-address:5000"  # Update to your actual server address

# Email notification settings
EMAIL_NOTIFICATIONS_ENABLED = True  # Set to False to disable email notifications
USE_SUPERVISOR_EMAIL = True  # Whether to use supervisor's email for notifications

# Outlook settings - uncomment if you need custom settings
# OUTLOOK_PROFILE = "Default"  # Optional: specify Outlook profile name

# Email templates location
EMAIL_TEMPLATES_DIR = "templates/email"  # Optional: location for HTML email templates


# Initialize Flask app
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = config.UPLOAD_FOLDER
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Configure logging with more detail
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT,
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Slack Events Adapter
slack_event_adapter = SlackEventAdapter(
    config.SLACK_SIGNING_SECRET, 
"/slack/events", 
    app
)

# Handle Home Tab Opened Event
@slack_event_adapter.on("app_home_opened")
def home_opened(event_data):
    user_id = event_data["event"]["user"]
    logger.info("Home tab opened by user %s", user_id)
    slack_client.update_home_tab(user_id)