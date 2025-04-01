"""
Database Diagnostic and Repair Tool for Slackabot
Save this as fix_database.py and run it to fix database issues
"""

import sqlite3
import logging
import traceback
import os
import sys
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("database_repair.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("database_repair")

# Database path - change if needed
DB_PATH = "logger.db"

def get_db_connection():
    """Get database connection with row factory enabled"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # This enables column access by name
    return conn

def manual_fix():
    """Manual database fix - direct SQL commands approach"""
    logger.info("Starting manual database fix...")
    conn = get_db_connection()
    
    try:
        # Step 1: Get the current columns from audits table
        conn.execute("BEGIN TRANSACTION")
        
        # Step 2: Create a new table with correct schema
        conn.execute('''
        CREATE TABLE IF NOT EXISTS new_audits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_slack_id TEXT NOT NULL,
            workday TEXT NOT NULL,
            login_time TEXT,
            logout_time TEXT,
            self_notified INTEGER DEFAULT 0,
            supervisor_notified INTEGER DEFAULT 0,
            second_supervisor_notified INTEGER DEFAULT 0,
            is_supervisor_acknowledged INTEGER DEFAULT 0,
            is_second_supervisor_acknowledged INTEGER DEFAULT 0,
            last_supervisor_notification_time TEXT,
            last_second_supervisor_notification_time TEXT,
            expected_login_time TEXT,
            email_supervisor_notified INTEGER DEFAULT 0,
            email_second_supervisor_notified INTEGER DEFAULT 0
        )
        ''')
        
        # Step 3: Copy data from audits table
        conn.execute('''
        INSERT INTO new_audits (
            user_slack_id, workday, login_time, logout_time, 
            self_notified, supervisor_notified, second_supervisor_notified,
            is_supervisor_acknowledged, is_second_supervisor_acknowledged,
            last_supervisor_notification_time, last_second_supervisor_notification_time,
            expected_login_time, email_supervisor_notified, email_second_supervisor_notified
        )
        SELECT 
            user_slack_id, workday, login_time, logout_time,
            COALESCE(self_notified, 0), COALESCE(supervisor_notified, 0), COALESCE(second_supervisor_notified, 0),
            COALESCE(is_supervisor_acknowledged, 0), COALESCE(is_second_supervisor_acknowledged, 0),
            last_supervisor_notification_time, last_second_supervisor_notification_time,
            expected_login_time, 
            COALESCE(email_supervisor_notified, 0), COALESCE(email_second_supervisor_notified, 0)
        FROM audits
        WHERE id IS NOT NULL
        ''')
        
        # Step 4: Find and copy records with NULL IDs
        conn.execute('''
        INSERT INTO new_audits (
            user_slack_id, workday, login_time, logout_time, 
            self_notified, supervisor_notified, second_supervisor_notified,
            is_supervisor_acknowledged, is_second_supervisor_acknowledged,
            last_supervisor_notification_time, last_second_supervisor_notification_time,
            expected_login_time, email_supervisor_notified, email_second_supervisor_notified
        )
        SELECT 
            user_slack_id, workday, login_time, logout_time,
            COALESCE(self_notified, 0), COALESCE(supervisor_notified, 0), COALESCE(second_supervisor_notified, 0),
            COALESCE(is_supervisor_acknowledged, 0), COALESCE(is_second_supervisor_acknowledged, 0),
            last_supervisor_notification_time, last_second_supervisor_notification_time,
            expected_login_time, 
            COALESCE(email_supervisor_notified, 0), COALESCE(email_second_supervisor_notified, 0)
        FROM audits a1
        WHERE id IS NULL
        AND NOT EXISTS (
            SELECT 1 FROM new_audits a2 
            WHERE a2.user_slack_id = a1.user_slack_id 
            AND a2.workday = a1.workday
        )
        ''')
        
        # Step 5: Drop the old table and rename the new one
        conn.execute("DROP TABLE audits")
        conn.execute("ALTER TABLE new_audits RENAME TO audits")
        
        # Step 6: Create the index if it doesn't exist
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audits_user_workday ON audits (user_slack_id, workday)")
        
        # Step 7: Create acknowledgment tokens table if it doesn't exist
        conn.execute("""
        CREATE TABLE IF NOT EXISTS acknowledgment_tokens (
            token TEXT PRIMARY KEY,
            user_slack_id TEXT NOT NULL,
            is_second_supervisor INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            used INTEGER DEFAULT 0
        )
        """)
        
        # Commit all changes
        conn.execute("COMMIT")
        logger.info("Manual database fix completed successfully")
        
        # Now fix specific user records
        fix_user_record("U06081ECKT3")
        
        return True
    except Exception as e:
        logger.error(f"Error during manual fix: {e}")
        logger.error(traceback.format_exc())
        try:
            conn.execute("ROLLBACK")
        except:
            pass
        return False
    finally:
        conn.close()

def fix_user_record(user_slack_id):
    """Create or fix records for a specific user"""
    logger.info(f"Fixing records for user {user_slack_id}")
    conn = get_db_connection()
    
    try:
        # Get expected login time
        cursor = conn.cursor()
        cursor.execute("SELECT user_login_time FROM users WHERE user_slack_id = ?", (user_slack_id,))
        user = cursor.fetchone()
        expected_login_time = user['user_login_time'] if user else None
        
        # Get today's date
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Check if record exists for today
        cursor.execute("SELECT id FROM audits WHERE user_slack_id = ? AND workday = ?", (user_slack_id, today))
        record = cursor.fetchone()
        
        if not record:
            # Create new record
            logger.info(f"Creating new record for user {user_slack_id} on {today}")
            conn.execute("BEGIN TRANSACTION")
            conn.execute(
                """
                INSERT INTO audits (
                    user_slack_id, workday, self_notified, supervisor_notified, 
                    second_supervisor_notified, is_supervisor_acknowledged,
                    is_second_supervisor_acknowledged, expected_login_time
                ) VALUES (?, ?, 0, 0, 0, 0, 0, ?)
                """,
                (user_slack_id, today, expected_login_time)
            )
            conn.execute("COMMIT")
            logger.info("Record created successfully")
        else:
            logger.info(f"Record already exists for user {user_slack_id} on {today} with ID {record['id']}")
        
        return True
    except Exception as e:
        logger.error(f"Error fixing user record: {e}")
        logger.error(traceback.format_exc())
        try:
            conn.execute("ROLLBACK")
        except:
            pass
        return False
    finally:
        conn.close()

def check_tables():
    """Check if all tables exist and have the correct structure"""
    logger.info("Checking database tables...")
    
    if not os.path.exists(DB_PATH):
        logger.error(f"Database file not found: {DB_PATH}")
        return False
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if users table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            logger.error("Users table does not exist!")
            return False
        
        # Check if audits table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audits'")
        if not cursor.fetchone():
            logger.error("Audits table does not exist!")
            return False
        
        # Check audits columns
        cursor.execute("PRAGMA table_info(audits)")
        columns = {column['name'] for column in cursor.fetchall()}
        
        required_columns = {
            "id", "user_slack_id", "workday", "login_time", "logout_time", "self_notified",
            "supervisor_notified", "second_supervisor_notified", "is_supervisor_acknowledged",
            "is_second_supervisor_acknowledged", "last_supervisor_notification_time",
            "last_second_supervisor_notification_time", "expected_login_time",
            "email_supervisor_notified", "email_second_supervisor_notified"
        }
        
        missing_columns = required_columns - columns
        if missing_columns:
            logger.error(f"Missing columns in audits table: {missing_columns}")
            return False
        
        # Check if id is primary key
        cursor.execute("PRAGMA table_info(audits)")
        id_is_pk = False
        for column in cursor.fetchall():
            if column['name'] == 'id' and column['pk'] == 1:
                id_is_pk = True
                break
        
        if not id_is_pk:
            logger.error("ID column is not set as primary key in audits table")
            return False
        
        logger.info("All tables exist and have the correct structure")
        return True
    except Exception as e:
        logger.error(f"Error checking tables: {e}")
        logger.error(traceback.format_exc())
        return False
    finally:
        conn.close()

def main():
    """Main function"""
    logger.info("Starting database repair...")
    
    # Check if all tables are correctly set up
    if check_tables():
        logger.info("Database is correctly structured, only fixing user records")
        
        # Fix user record if specified
        if len(sys.argv) > 1:
            user_slack_id = sys.argv[1]
            fix_user_record(user_slack_id)
        else:
            # Fix specific problematic user
            fix_user_record("U06081ECKT3")
    else:
        logger.info("Database needs structural repair, performing manual fix")
        manual_fix()
    
    logger.info("Database repair completed")

if __name__ == "__main__":
    main()