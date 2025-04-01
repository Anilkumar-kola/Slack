"""
Database connection, initialization, and query functionality for the Slack Attendance Bot.
"""

import logging
import sqlite3
import traceback
from datetime import datetime, timedelta

import config
import utils

logger = logging.getLogger(__name__)

def get_db_connection():
    """
    Create and return a database connection with row factory enabled.
    
    Returns:
        sqlite3.Connection: An active database connection
    """
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # This enables column access by name
    return conn

def init_database():
    """
    Initialize the database by creating necessary tables if they don't exist.
    Also handles database schema migrations for new columns.
    All schema changes are performed in a single transaction.
    """
    logger.info("Initializing database...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Begin transaction
        cursor.execute("BEGIN TRANSACTION")
        
        # Create the users table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_slack_id TEXT NOT NULL,
            user_name TEXT NOT NULL,
            user_email_id TEXT,
            user_whatsapp_number TEXT,
            user_login_time TEXT,
            user_logout_time TEXT,
            supervisor_name TEXT,
            supervisor_email_id TEXT,
            supervisor_slack_id TEXT,
            supervisor_whatsapp_number TEXT,
            second_supervisor_name TEXT,
            second_supervisor_slack_id TEXT,
            second_supervisor_email_id TEXT,
            second_supervisor_whatsapp_number TEXT
        )
        ''')
        
        # Create the audits table if it doesn't exist with only necessary columns
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS audits (
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
        
        # Create the acknowledgment_tokens table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS acknowledgment_tokens (
            token TEXT PRIMARY KEY,
            user_slack_id TEXT NOT NULL,
            is_second_supervisor INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            used INTEGER DEFAULT 0
        )
        """)
        
        # Create indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audits_user_workday ON audits (user_slack_id, workday)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_login_time ON users (user_login_time)")
        
        # Commit the transaction
        conn.commit()
        logger.info("Database initialized successfully")
        
        # Now, let's clean up duplicate columns
        clean_duplicate_columns()
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error initializing database: {e}")
        logger.error(traceback.format_exc())
        raise
    finally:
        conn.close()

def clean_duplicate_columns():
    """
    Clean up duplicate columns in the audits table.
    This should be run after the database is initialized.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get all columns in the audits table
        cursor.execute("PRAGMA table_info(audits)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # List of duplicate columns to remove
        duplicate_columns = [
            "self_email_notified",
            "supervisor_email_notified",  # Use email_supervisor_notified instead
            "last_notification_time",  # Use specific notification time columns
            "email_self_notified",  # Duplicate of self_email_notified
            "supervisor_name",  # Should be in users table, not audits
            "second_supervisor_name",  # Should be in users table, not audits
            "is_email_acknowledged",  # Use is_supervisor_acknowledged and is_second_supervisor_acknowledged
            "second_acknowledgment_token"  # Use acknowledgment_tokens table
        ]
        
        # Check which duplicates exist
        existing_duplicates = [col for col in duplicate_columns if col in columns]
        
        if existing_duplicates:
            logger.info(f"Found duplicate columns to clean up: {existing_duplicates}")
            
            # Create a new table without the duplicate columns
            cursor.execute("BEGIN TRANSACTION")
            
            # Construct the column list for the new table
            keep_columns = [col for col in columns if col not in existing_duplicates]
            column_list = ", ".join(keep_columns)
            
            # Create a new table without the duplicate columns
            cursor.execute(f"""
            CREATE TABLE audits_new (
                {', '.join([f"{col[1]} {col[2]}" for col in cursor.execute("PRAGMA table_info(audits)").fetchall() 
                           if col[1] not in existing_duplicates])}
            )
            """)
            
            # Copy data to the new table
            cursor.execute(f"INSERT INTO audits_new SELECT {column_list} FROM audits")
            
            # Drop the old table and rename the new one
            cursor.execute("DROP TABLE audits")
            cursor.execute("ALTER TABLE audits_new RENAME TO audits")
            
            # Recreate indexes
            cursor.execute("CREATE INDEX idx_audits_user_workday ON audits (user_slack_id, workday)")
            
            cursor.execute("COMMIT")
            logger.info("Successfully cleaned up duplicate columns in audits table")
        else:
            logger.info("No duplicate columns found in audits table")
    
    except Exception as e:
        logger.error(f"Error cleaning up duplicate columns: {e}")
        logger.error(traceback.format_exc())
        try:
            cursor.execute("ROLLBACK")
        except:
            pass
    finally:
        conn.close()

def get_user_by_slack_id(slack_id):
    """
    Get a user record by their Slack ID
    
    Args:
        slack_id (str): The user's Slack ID
    
    Returns:
        dict: User record or None if not found
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM users WHERE user_slack_id = ?", (slack_id,))
        user = cursor.fetchone()
        return dict(user) if user else None
    except Exception as e:
        logger.error(f"Error getting user by Slack ID {slack_id}: {e}")
        logger.error(traceback.format_exc())
        return None
    finally:
        conn.close()

def store_acknowledgment_token(token, user_slack_id, is_second_supervisor=False):
    """
    Store an acknowledgment token in the database
    
    Args:
        token (str): The unique token
        user_slack_id (str): The user's Slack ID
        is_second_supervisor (bool): Whether this is for the second supervisor
    
    Returns:
        bool: True if successful
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("BEGIN TRANSACTION")
        
        # First check if we need to create the table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS acknowledgment_tokens (
            token TEXT PRIMARY KEY,
            user_slack_id TEXT NOT NULL,
            is_second_supervisor INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            used INTEGER DEFAULT 0
        )
        """)
        
        # Store the token
        cursor.execute(
            """
            INSERT INTO acknowledgment_tokens (token, user_slack_id, is_second_supervisor, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (token, user_slack_id, 1 if is_second_supervisor else 0, utils.get_current_datetime_str())
        )
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Error storing acknowledgment token: {e}")
        logger.error(traceback.format_exc())
        return False
    finally:
        conn.close()

def get_acknowledgment_token(token):
    """
    Get an acknowledgment token from the database
    
    Args:
        token (str): The token to retrieve
    
    Returns:
        dict: Token data or None if not found
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "SELECT * FROM acknowledgment_tokens WHERE token = ?",
            (token,)
        )
        token_data = cursor.fetchone()
        return dict(token_data) if token_data else None
    except Exception as e:
        logger.error(f"Error getting acknowledgment token: {e}")
        logger.error(traceback.format_exc())
        return None
    finally:
        conn.close()

def mark_token_used(token):
    """
    Mark a token as used
    
    Args:
        token (str): The token to mark as used
    
    Returns:
        bool: True if successful
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("BEGIN TRANSACTION")
        cursor.execute(
            "UPDATE acknowledgment_tokens SET used = 1 WHERE token = ?",
            (token,)
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Error marking token as used: {e}")
        logger.error(traceback.format_exc())
        return False
    finally:
        conn.close()

def get_user(user_slack_id):
    """
    Get user information from the database.
    
    Args:
        user_slack_id (str): The Slack ID of the user
        
    Returns:
        dict: User information or None if not found
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM users WHERE user_slack_id = ?",
            (user_slack_id,)
        )
        user = cursor.fetchone()
        return dict(user) if user else None
    except Exception as e:
        logger.error(f"Error getting user {user_slack_id}: {e}")
        logger.error(traceback.format_exc())
        return None
    finally:
        conn.close()

def get_audit_record(user_slack_id, workday):
    """
    Get audit record for a specific user and workday.
    
    Args:
        user_slack_id (str): The Slack ID of the user
        workday (str): The workday in format YYYY-MM-DD
        
    Returns:
        dict: Audit record or None if not found
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # First check if the record exists and has a valid ID
        cursor.execute(
            "SELECT id FROM audits WHERE user_slack_id = ? AND workday = ?",
            (user_slack_id, workday)
        )
        id_check = cursor.fetchone()
        
        if not id_check or id_check[0] is None:
            logger.warning(f"Audit record exists but has no valid ID for user {user_slack_id} on {workday}. Attempting to fix.")
            
            # Try to fix the record by ensuring it has a valid ID
            try:
                cursor.execute("BEGIN TRANSACTION")
                
                # First check if the record truly exists
                cursor.execute(
                    "SELECT COUNT(*) FROM audits WHERE user_slack_id = ? AND workday = ?",
                    (user_slack_id, workday)
                )
                count = cursor.fetchone()[0]
                
                if count > 0:
                    # Record exists but has no ID or invalid ID - delete and recreate it
                    cursor.execute(
                        "DELETE FROM audits WHERE user_slack_id = ? AND workday = ?",
                        (user_slack_id, workday)
                    )
                    logger.info(f"Deleted invalid audit record for {user_slack_id} on {workday}")
                    
                    # Get user's expected login time
                    cursor.execute(
                        "SELECT user_login_time FROM users WHERE user_slack_id = ?",
                        (user_slack_id,)
                    )
                    user = cursor.fetchone()
                    expected_login_time = user[0] if user else None
                    
                    # Create a new record with proper ID
                    cursor.execute(
                        """INSERT INTO audits 
                        (user_slack_id, workday, self_notified, supervisor_notified, 
                        second_supervisor_notified, is_supervisor_acknowledged, 
                        is_second_supervisor_acknowledged, expected_login_time) 
                        VALUES (?, ?, 0, 0, 0, 0, 0, ?)""",
                        (user_slack_id, workday, expected_login_time)
                    )
                    
                    new_id = cursor.lastrowid
                    logger.info(f"Created new record with ID {new_id} for {user_slack_id} on {workday}")
                
                cursor.execute("COMMIT")
            except Exception as e:
                cursor.execute("ROLLBACK")
                logger.error(f"Error fixing audit record: {e}")
                logger.error(traceback.format_exc())

        # Now get the full record with all columns
        cursor.execute(
            "SELECT * FROM audits WHERE user_slack_id = ? AND workday = ?",
            (user_slack_id, workday)
        )
        record = cursor.fetchone()
        
        if record:
            record_dict = dict(record)
            # Double-check that we have an ID
            if 'id' not in record_dict or record_dict['id'] is None:
                logger.error(f"Still cannot retrieve valid ID for audit record after fix attempt: {user_slack_id} on {workday}")
                return None
            return record_dict
        return None
    except Exception as e:
        logger.error(f"Error getting audit record for {user_slack_id} on {workday}: {e}")
        logger.error(traceback.format_exc())
        return None
    finally:
        conn.close()

def create_audit_record(user_slack_id, workday, expected_login_time):
    """
    Create a new audit record for a user.
    
    Args:
        user_slack_id (str): The Slack ID of the user
        workday (str): The workday in format YYYY-MM-DD
        expected_login_time (str): The expected login time
        
    Returns:
        int: The ID of the created record
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # First check if a record already exists
        cursor.execute(
            "SELECT id FROM audits WHERE user_slack_id = ? AND workday = ?",
            (user_slack_id, workday)
        )
        existing = cursor.fetchone()
        
        if existing and existing[0] is not None:
            # Record already exists with valid ID
            logger.info(f"Audit record already exists with ID {existing[0]} for user {user_slack_id} on {workday}")
            return existing[0]
        
        # Delete any records without valid IDs
        cursor.execute("BEGIN TRANSACTION")
        cursor.execute(
            "DELETE FROM audits WHERE user_slack_id = ? AND workday = ?",
            (user_slack_id, workday)
        )
        
        # Insert new record
        cursor.execute(
            """INSERT INTO audits 
               (user_slack_id, workday, self_notified, supervisor_notified, 
                second_supervisor_notified, is_supervisor_acknowledged,
                is_second_supervisor_acknowledged, expected_login_time) 
               VALUES (?, ?, 0, 0, 0, 0, 0, ?)""",
            (user_slack_id, workday, expected_login_time)
        )
        
        record_id = cursor.lastrowid
        
        # Verify the record was created with a valid ID
        cursor.execute(
            "SELECT id FROM audits WHERE user_slack_id = ? AND workday = ?",
            (user_slack_id, workday)
        )
        verification = cursor.fetchone()
        
        if verification and verification[0] is not None:
            conn.commit()
            logger.info(f"Created audit record {record_id} for user {user_slack_id} on {workday}")
            return record_id
        else:
            conn.rollback()
            logger.error(f"Failed to create audit record with valid ID for {user_slack_id} on {workday}")
            raise Exception("Failed to create audit record with valid ID")
            
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating audit record for {user_slack_id}: {e}")
        logger.error(traceback.format_exc())
        raise
    finally:
        conn.close()

def update_user_login(user_slack_id, workday, login_time):
    """
    Update the login time for a user in the audits table.
    Creates an audit record if one doesn't exist.
    
    Args:
        user_slack_id (str): The Slack ID of the user
        workday (str): The workday in format YYYY-MM-DD
        login_time (str): The login time in format HH:MM:SS
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("BEGIN TRANSACTION")
        
        # Check if audit record exists
        cursor.execute(
            "SELECT id FROM audits WHERE user_slack_id = ? AND workday = ?",
            (user_slack_id, workday)
        )
        record = cursor.fetchone()
        
        if record:
            # Update existing record
            audit_id = record[0]
            cursor.execute(
                "UPDATE audits SET login_time = ? WHERE id = ?",
                (login_time, audit_id)
            )
            logger.info(f"Updated login time to {login_time} for user {user_slack_id} on {workday}")
        else:
            # Get user's expected login time
            cursor.execute(
                "SELECT user_login_time FROM users WHERE user_slack_id = ?",
                (user_slack_id,)
            )
            user = cursor.fetchone()
            expected_login_time = user[0] if user else None
            
            # Create new audit record
            cursor.execute(
                """INSERT INTO audits 
                (user_slack_id, workday, login_time, self_notified, 
                supervisor_notified, second_supervisor_notified, 
                is_supervisor_acknowledged, is_second_supervisor_acknowledged, 
                expected_login_time) 
                VALUES (?, ?, ?, 0, 0, 0, 0, 0, ?)""",
                (user_slack_id, workday, login_time, expected_login_time)
            )
            logger.info(f"Created new audit record with login time {login_time} for user {user_slack_id} on {workday}")
        
        # Verify the update was successful
        cursor.execute(
            "SELECT login_time FROM audits WHERE user_slack_id = ? AND workday = ?", 
            (user_slack_id, workday)
        )
        verification = cursor.fetchone()
        
        if verification and verification[0] == login_time:
            conn.commit()
            return True
        else:
            conn.rollback()
            logger.error(f"Failed to update login time for user {user_slack_id}")
            return False
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating login time for user {user_slack_id}: {e}")
        logger.error(traceback.format_exc())
        return False
    finally:
        conn.close()

def record_user_login(user_slack_id):
    """
    Record a user login at the current time.
    
    Args:
        user_slack_id (str): The Slack ID of the user
        
    Returns:
        bool: True if recording was successful, False otherwise
    """
    # Get current date and time
    now = datetime.now()
    workday = now.strftime("%Y-%m-%d")
    login_time = now.strftime("%Y-%m-%d %H:%M")
    
    # Update the login time
    return update_user_login(user_slack_id, workday, login_time)

def record_user_logout(user_slack_id):
    """
    Record a user logout at the current time.
    
    Args:
        user_slack_id (str): The Slack ID of the user
        
    Returns:
        bool: True if recording was successful, False otherwise
    """
    # Get current date and time
    now = datetime.now()
    workday = now.strftime("%Y-%m-%d")
    logout_time = now.strftime("%Y-%m-%d %H:%M")
    
    # Update the logout time
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("BEGIN TRANSACTION")
        
        # Check if audit record exists
        cursor.execute(
            "SELECT id FROM audits WHERE user_slack_id = ? AND workday = ?",
            (user_slack_id, workday)
        )
        record = cursor.fetchone()
        
        if record:
            # Update existing record
            audit_id = record[0]
            cursor.execute(
                "UPDATE audits SET logout_time = ? WHERE id = ?",
                (logout_time, audit_id)
            )
            logger.info(f"Updated logout time to {logout_time} for user {user_slack_id} on {workday}")
        else:
            # Get user's expected login time
            cursor.execute(
                "SELECT user_login_time FROM users WHERE user_slack_id = ?",
                (user_slack_id,)
            )
            user = cursor.fetchone()
            expected_login_time = user[0] if user else None
            
            # Create new audit record with logout time only
            cursor.execute(
                """INSERT INTO audits 
                (user_slack_id, workday, logout_time, self_notified, 
                supervisor_notified, second_supervisor_notified, 
                is_supervisor_acknowledged, is_second_supervisor_acknowledged, 
                expected_login_time) 
                VALUES (?, ?, ?, 0, 0, 0, 0, 0, ?)""",
                (user_slack_id, workday, logout_time, expected_login_time)
            )
            logger.info(f"Created new audit record with logout time {logout_time} for user {user_slack_id} on {workday}")
        
        # Verify the update was successful
        cursor.execute(
            "SELECT logout_time FROM audits WHERE user_slack_id = ? AND workday = ?", 
            (user_slack_id, workday)
        )
        verification = cursor.fetchone()
        
        if verification and verification[0] == logout_time:
            conn.commit()
            return True
        else:
            conn.rollback()
            logger.error(f"Failed to update logout time for user {user_slack_id}")
            return False
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating logout time for user {user_slack_id}: {e}")
        logger.error(traceback.format_exc())
        return False
    finally:
        conn.close()

def find_unacknowledged_audit_record(user_slack_id, is_secondary):
    """
    Find the most recent unacknowledged audit record for a given supervisor
    
    Args:
        user_slack_id (str): Slack ID of the supervisor
        is_secondary (bool): Whether searching for secondary supervisor
    
    Returns:
        dict: Audit record or None
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if is_secondary:
            # Find unacknowledged record with second supervisor slack ID
            cursor.execute(
                """
                SELECT a.* 
                FROM audits a
                JOIN users u ON a.user_slack_id = u.user_slack_id
                WHERE u.second_supervisor_slack_id = ?
                AND a.second_supervisor_notified > 0 
                AND a.is_second_supervisor_acknowledged = 0
                ORDER BY a.id DESC
                LIMIT 1
                """, 
                (user_slack_id,)
            )
        else:
            # Find unacknowledged record with primary supervisor slack ID
            cursor.execute(
                """
                SELECT a.* 
                FROM audits a
                JOIN users u ON a.user_slack_id = u.user_slack_id
                WHERE u.supervisor_slack_id = ?
                AND a.supervisor_notified > 0 
                AND a.is_supervisor_acknowledged = 0
                ORDER BY a.id DESC
                LIMIT 1
                """, 
                (user_slack_id,)
            )
        
        record = cursor.fetchone()
        return dict(record) if record else None
    
    except Exception as e:
        logger.error(f"Error finding unacknowledged audit record: {e}")
        logger.error(traceback.format_exc())
        return None
    finally:
        conn.close()

def update_audit_record(audit_id, **kwargs):
    """
    Update fields in an audit record.
    
    Args:
        audit_id (int): The ID of the audit record
        **kwargs: Field-value pairs to update
    """
    if not kwargs:
        return
        
    if audit_id is None:
        logger.error("Cannot update audit record: audit_id is None")
        return False
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
        values = list(kwargs.values())
        values.append(audit_id)
        
        logger.info(f"Updating audit record {audit_id} with {kwargs}")
        
        cursor.execute("BEGIN TRANSACTION")
        cursor.execute(
            f"UPDATE audits SET {set_clause} WHERE id = ?",
            values
        )
        
        # Verify the update was successful
        if kwargs:
            # Only execute verification if there are fields to select
            fields_list = list(kwargs.keys())
            if fields_list:
                fields = ", ".join(fields_list)
                cursor.execute(f"SELECT {fields} FROM audits WHERE id = ?", (audit_id,))
                verification = cursor.fetchone()
                
                if verification:
                    conn.commit()
                    logger.info(f"Successfully updated audit record {audit_id}")
                    return True
                else:
                    conn.rollback()
                    logger.error(f"Failed to update audit record {audit_id} - verification failed")
                    return False
        
        # Commit without verification if we get here
        conn.commit()
        logger.info(f"Successfully updated audit record {audit_id}")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating audit record {audit_id}: {e}")
        logger.error(traceback.format_exc())
        return False
    finally:
        conn.close()

def get_users_without_login():
    """
    Get all users who are expected to have logged in by now but haven't.
    
    Returns:
        list: List of user records
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        today = now.strftime("%Y-%m-%d")
        
        cursor.execute(
            """
            SELECT u.user_slack_id, u.user_name, u.user_login_time, u.supervisor_slack_id, 
                   u.second_supervisor_slack_id, u.supervisor_email_id, u.second_supervisor_email_id
            FROM users u
            WHERE u.user_login_time IS NOT NULL AND u.user_login_time <= ?
            AND (
                u.user_slack_id NOT IN (SELECT user_slack_id FROM audits WHERE workday = ? AND login_time IS NOT NULL)
                OR
                u.user_slack_id IN (SELECT user_slack_id FROM audits WHERE login_time IS NULL AND workday = ?)
            )
            """,
            (current_time, today, today)
        )
        
        users = [dict(row) for row in cursor.fetchall()]
        return users
    except Exception as e:
        logger.error(f"Error getting users without login: {e}")
        logger.error(traceback.format_exc())
        return []
    finally:
        conn.close()

def check_database_integrity():
    """
    Check database integrity and return issues found.
    
    Returns:
        dict: Issues found or empty dict if none
    """
    issues = {}
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if all required columns exist in audits table
        cursor.execute("PRAGMA table_info(audits)")
        columns = {column[1] for column in cursor.fetchall()}
        
        required_columns = {
            "second_supervisor_notified",
            "is_second_supervisor_acknowledged",
            "last_supervisor_notification_time",
            "last_second_supervisor_notification_time",
            "expected_login_time",
            "email_supervisor_notified",
            "email_second_supervisor_notified"
        }
        
        missing_columns = required_columns - columns
        if missing_columns:
            issues["missing_columns"] = list(missing_columns)
        
        # Check for stuck records
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute(
            """
            SELECT COUNT(*) FROM audits 
            WHERE workday = ? 
            AND supervisor_notified > 0 
            AND second_supervisor_notified = 0
            AND is_supervisor_acknowledged = 0
            """,
            (today,)
        )
        stuck_records = cursor.fetchone()[0]
        if stuck_records > 0:
            issues["stuck_records"] = stuck_records
        
        return issues
    except Exception as e:
        logger.error(f"Error checking database integrity: {e}")
        logger.error(traceback.format_exc())
        issues["error"] = str(e)
        return issues
    finally:
        conn.close()

def fix_stuck_records():
    """
    Fix stuck records by resetting notification flags.
    
    Returns:
        dict: Status of the fix operation
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("BEGIN TRANSACTION")
        
        # Find stuck records
        cursor.execute(
            """
            SELECT id FROM audits 
            WHERE workday = ? 
            AND supervisor_notified > 0 
            AND second_supervisor_notified = 0
            AND is_supervisor_acknowledged = 0
            """,
            (today,)
        )
        
        stuck_ids = [row[0] for row in cursor.fetchall()]
        fixed_count = 0
        
        for audit_id in stuck_ids:
            # Reset the record to force rechecking
            cursor.execute(
                """
                UPDATE audits SET 
                    second_supervisor_notified = 0,
                    is_second_supervisor_acknowledged = 0,
                    last_supervisor_notification_time = ?
                WHERE id = ?
                """,
                (utils.get_current_datetime_str(), audit_id)
            )
            fixed_count += 1
        
        conn.commit()
        return {"fixed_count": fixed_count, "status": "success"}
    except Exception as e:
        conn.rollback()
        logger.error(f"Error fixing stuck records: {e}")
        logger.error(traceback.format_exc())
        return {"status": "error", "error": str(e)}
    finally:
        conn.close()