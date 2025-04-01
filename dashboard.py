"""
Streamlit dashboard for Slack Attendance Bot.
Provides a web interface for managing users and viewing attendance data.
"""

import os
import pandas as pd
import streamlit as st
import sqlite3
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import json



st.set_page_config(
    page_title="Slack Attendance Dashboard",
    page_icon="⏰",
    layout="wide",
    initial_sidebar_state="expanded",
)
# Add session state variables
if 'show_success' not in st.session_state:
    st.session_state.show_success = False
if 'form_submitted' not in st.session_state:
    st.session_state.form_submitted = False
# Set page configuration - MUST BE THE FIRST STREAMLIT COMMAND
# Add second_supervisor_name column if it doesn't exist
def ensure_second_supervisor_name_column():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in cursor.fetchall()]
            if "second_supervisor_name" not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN second_supervisor_name TEXT")
                conn.commit()
                st.success("Database schema updated with second_supervisor_name field")
            conn.close()
        except Exception as e:
            st.error(f"Database schema update error: {str(e)}")
            if conn:
                conn.close()

# Skip Excel and use CSV only to avoid openpyxl issues
EXCEL_SUPPORT = False
st.info("Using CSV export format for compatibility.")

# Try to import other optional dependencies
try:
    import utils
except ImportError:
    # Create minimal utils module if not found
    class UtilsModule:
        def convert_to_datetime(self, time_str):
            if not time_str:
                return ""
            return time_str
    utils = UtilsModule()

# Import database module without triggering initialization
try:
    import sys
    import importlib.util
    spec = importlib.util.spec_from_file_location("database", "database.py")
    database = importlib.util.module_from_spec(spec)
    sys.modules["database"] = database
    spec.loader.exec_module(database)
except Exception as e:
    st.error(f"Error loading database module: {str(e)}")

# Apply custom CSS
st.markdown("""
<style>
    .main .block-container {
        padding-top: 2rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        background-color: #f0f2f6;
    }
    .stTabs [aria-selected="true"] {
        background-color: #4CAF50;
        color: white;
    }
    .highlight {
        background-color: #f8f9fa;
        border-radius: 5px;
        padding: 15px;
        margin: 10px 0;
    }
    .warning {
        color: #ff4b4b;
        font-weight: bold;
    }
    .success {
        color: #00ab41;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Function to get database connection
def get_db_connection():
    try:
        conn = sqlite3.connect("logger.db")
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        st.error(f"Database connection error: {str(e)}")
        return None

# Function to export data as CSV only (avoiding Excel compatibility issues)
def export_data(data, filename):
    # CSV export only for compatibility
    csv_buffer = BytesIO()
    data.to_csv(csv_buffer, index=False)
    csv_data = csv_buffer.getvalue()
    
    return st.download_button(
        label="Download Data as CSV",
        data=csv_data,
        file_name=filename + ".csv",
        mime="text/csv"
    )

# Run schema update
ensure_second_supervisor_name_column()

# Create title
st.title("Slack Attendance Dashboard")

# Create sidebar
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2097/2097068.png", width=100)
st.sidebar.title("Navigation")

# Navigation options
page = st.sidebar.radio(
    "Go to",
    ["User Management", "Attendance Records", "Analytics", "Settings"]
)

# Display current time
st.sidebar.markdown("---")
st.sidebar.markdown(f"**Current Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# User Management Page
if page == "User Management":
    st.header("User Management")
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["View & Edit Users", "Add New User", "Bulk Import/Export"])
    
    # Tab 1: View and Edit Users
    with tab1:
        st.subheader("All Users")
        
        # Get users from database
        conn = get_db_connection()
        if conn:
            try:
                df_users = pd.read_sql_query("SELECT * FROM users", conn)
                conn.close()
                
                # Format the dataframe for display
                display_cols = [
                    'user_id', 'user_name', 'user_slack_id', 'user_email_id', 
                    'user_login_time', 'user_logout_time', 'supervisor_name',
                    'supervisor_email_id', 'supervisor_slack_id', 'second_supervisor_slack_id'
                ]
                
                # Display users with edit option
                with st.container():
                    # Filters
                    col1, col2 = st.columns(2)
                    with col1:
                        search_term = st.text_input("Search by name", "")
                    with col2:
                        filter_option = st.selectbox(
                            "Filter by supervisor", 
                            ["All"] + list(df_users['supervisor_name'].dropna().unique())
                        )
                    
                    # Apply filters
                    filtered_df = df_users.copy()
                    if search_term:
                        filtered_df = filtered_df[filtered_df['user_name'].str.contains(search_term, case=False, na=False)]
                    if filter_option != "All":
                        filtered_df = filtered_df[filtered_df['supervisor_name'] == filter_option]
                    
                    # Display table with edit button
                    for index, row in filtered_df.iterrows():
                        with st.expander(f"{row['user_name']} ({row['user_slack_id']})"):
                            with st.form(f"edit_user_{row['user_id']}"):
                                cols = st.columns(2)
                                
                                # Column 1
                                with cols[0]:
                                    name = st.text_input("Name", row['user_name'])
                                    slack_id = st.text_input("Slack ID", row['user_slack_id'])
                                    email = st.text_input("Email", row['user_email_id'] or "")
                                    whatsapp = st.text_input("WhatsApp", row.get('user_whatsapp_number', "") or "")
                                    login_time = st.text_input("Login Time (HH:MM)", row['user_login_time'] or "")
                                    logout_time = st.text_input("Logout Time (HH:MM)", row['user_logout_time'] or "")
                                    
                                # Column 2
                                with cols[1]:
                                    supervisor_name = st.text_input("Supervisor Name", row['supervisor_name'] or "")
                                    supervisor_email = st.text_input("Supervisor Email", row.get('supervisor_email_id', "") or "")
                                    supervisor_slack_id = st.text_input("Supervisor Slack ID", row['supervisor_slack_id'] or "")
                                    supervisor_whatsapp = st.text_input("Supervisor WhatsApp", row.get('supervisor_whatsapp_number', "") or "")
                                    second_supervisor_name = st.text_input("Second Supervisor Name", row.get('second_supervisor_name', "") or "")
                                    second_supervisor_slack_id = st.text_input("Second Supervisor Slack ID", row.get('second_supervisor_slack_id', "") or "")
                                    second_supervisor_email = st.text_input("Second Supervisor Email", row.get('second_supervisor_email_id', "") or "")
                                
                                # Save and Delete buttons
                                col1, col2 = st.columns(2)
                                with col1:
                                    save = st.form_submit_button("Save Changes")
                                with col2:
                                    delete = st.form_submit_button("Delete User", type="secondary")
                                
                                # Handle save
                                if save:
                                    conn = get_db_connection()
                                    if conn:
                                        try:
                                            cursor = conn.cursor()
                                            cursor.execute(
                                                """
                                                UPDATE users SET
                                                    user_name = ?,
                                                    user_slack_id = ?,
                                                    user_email_id = ?,
                                                    user_whatsapp_number = ?,
                                                    user_login_time = ?,
                                                    user_logout_time = ?,
                                                    supervisor_name = ?,
                                                    supervisor_email_id = ?,
                                                    supervisor_slack_id = ?,
                                                    supervisor_whatsapp_number = ?,
                                                    second_supervisor_name = ?,
                                                    second_supervisor_slack_id = ?,
                                                    second_supervisor_email_id = ?
                                                WHERE user_id = ?
                                                """,
                                                (
                                                    name, slack_id, email, whatsapp, 
                                                    login_time, logout_time,
                                                    supervisor_name, supervisor_email, 
                                                    supervisor_slack_id, supervisor_whatsapp,
                                                    second_supervisor_name,
                                                    second_supervisor_slack_id, second_supervisor_email,
                                                    row['user_id']
                                                )
                                            )
                                            conn.commit()
                                            conn.close()
                                            st.success("User updated successfully!")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Error updating user: {str(e)}")
                                            if conn:
                                                conn.close()
                                
                                # Handle delete
                                if delete:
                                    conn = get_db_connection()
                                    if conn:
                                        try:
                                            cursor = conn.cursor()
                                            cursor.execute("DELETE FROM users WHERE user_id = ?", (row['user_id'],))
                                            conn.commit()
                                            conn.close()
                                            st.success("User deleted successfully!")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Error deleting user: {str(e)}")
                                            if conn:
                                                conn.close()
            except Exception as e:
                st.error(f"Error loading users: {str(e)}")
                if conn:
                    conn.close()
        else:
            st.error("Failed to connect to database")
    
    # Tab 2: Add New User - FIXED CODE
    with tab2:
        st.subheader("Add New User")
        
        # Show success message if flag is set
        if st.session_state.show_success:
            st.success("User added successfully!")
            st.session_state.show_success = False

        # Reset form fields if previously submitted
        if st.session_state.form_submitted:
            st.session_state.form_submitted = False
            # Clear form fields
            for key in st.session_state.keys():
                if key.startswith('form_'):
                    st.session_state[key] = ""
            
        # Add user form - now correctly indented
        with st.form("add_user_form"):
            cols = st.columns(2)
            
            # Column 1 - added keys to all fields
            with cols[0]:
                new_name = st.text_input("Name", key="form_name", value=st.session_state.get('form_name', ""))
                new_slack_id = st.text_input("Slack ID", key="form_slack_id", value=st.session_state.get('form_slack_id', ""))
                new_email = st.text_input("Email", key="form_email", value=st.session_state.get('form_email', ""))
                new_whatsapp = st.text_input("WhatsApp Number", key="form_whatsapp", value=st.session_state.get('form_whatsapp', ""))
                new_login_time = st.text_input("Login Time (HH:MM)", key="form_login_time", value=st.session_state.get('form_login_time', ""))
                new_logout_time = st.text_input("Logout Time (HH:MM)", key="form_logout_time", value=st.session_state.get('form_logout_time', ""))
                
            # Column 2 - added keys to all fields
            with cols[1]:
                new_supervisor_name = st.text_input("Supervisor Name", key="form_supervisor_name", value=st.session_state.get('form_supervisor_name', ""))
                new_supervisor_email = st.text_input("Supervisor Email", key="form_supervisor_email", value=st.session_state.get('form_supervisor_email', ""))
                new_supervisor_slack_id = st.text_input("Supervisor Slack ID", key="form_supervisor_slack_id", value=st.session_state.get('form_supervisor_slack_id', ""))
                new_supervisor_whatsapp = st.text_input("Supervisor WhatsApp", key="form_supervisor_whatsapp", value=st.session_state.get('form_supervisor_whatsapp', ""))
                new_second_supervisor_name = st.text_input("Second Supervisor Name", key="form_second_supervisor_name", value=st.session_state.get('form_second_supervisor_name', ""))
                new_second_supervisor_slack_id = st.text_input("Second Supervisor Slack ID", key="form_second_supervisor_slack_id", value=st.session_state.get('form_second_supervisor_slack_id', ""))
                new_second_supervisor_email = st.text_input("Second Supervisor Email", key="form_second_supervisor_email", value=st.session_state.get('form_second_supervisor_email', ""))
            
            # Submit button
            submit = st.form_submit_button("Add User")
            
            # Handle form submission
            if submit:
                if not new_name or not new_slack_id:
                    st.error("Name and Slack ID are required fields.")
                else:
                    conn = get_db_connection()
                    if conn:
                        try:
                            cursor = conn.cursor()
                            cursor.execute(
                                """
                                INSERT INTO users (
                                    user_name, user_slack_id, user_email_id, user_whatsapp_number,
                                    user_login_time, user_logout_time, supervisor_name,
                                    supervisor_email_id, supervisor_slack_id, supervisor_whatsapp_number,
                                    second_supervisor_name, second_supervisor_slack_id, second_supervisor_email_id
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    new_name, new_slack_id, new_email, new_whatsapp,
                                    new_login_time, new_logout_time, new_supervisor_name,
                                    new_supervisor_email, new_supervisor_slack_id, new_supervisor_whatsapp,
                                    new_second_supervisor_name, new_second_supervisor_slack_id, new_second_supervisor_email
                                )
                            )
                            conn.commit()
                            conn.close()
                            st.session_state.show_success = True
                            st.session_state.form_submitted = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error adding user: {str(e)}")
                            if conn:
                                conn.close()
                                
    
    # Tab 3: Bulk Import/Export
    with tab3:
        st.subheader("Bulk Import/Export")
        
        # Download template
        st.markdown("### Download Template")

        # Create template dataframe
        template_df = pd.DataFrame({
            "User Name": ["John Doe", "Jane Smith"],
            "Slack ID": ["U12345678", "U87654321"],
            "User Email ID": ["john@example.com", "jane@example.com"],
            "User WhatsApp Number": ["1234567890", "0987654321"],
            "User Login Time": ["09:00", "10:00"],
            "User Logout Time": ["17:00", "18:00"],
            "Supervisor Name": ["Super Visor", "Super Visor"],
            "Supervisor Email ID": ["super@example.com", "super@example.com"],
            "Supervisor Slack ID": ["U11111111", "U11111111"],
            "Supervisor WhatsApp Number": ["1111111111", "1111111111"],
            "Second Supervisor Name": ["Second Super", "Second Super"],
            "Second Supervisor Slack ID": ["U22222222", "U22222222"],
            "Second Supervisor Email ID": ["second@example.com", "second@example.com"]
        })

        # Convert to CSV directly
        csv_buffer = BytesIO()
        template_df.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue()

        # Provide download button
        st.download_button(
            label="Download Template as CSV",
            data=csv_data,
            file_name="user_template.csv",
            mime="text/csv"
        )
        
        # Upload Excel file
        st.markdown("### Upload Excel File")
        uploaded_file = st.file_uploader("Choose an Excel file", type=["xlsx", "xls", "csv"])
        
        if uploaded_file is not None:
            try:
                # Read the file based on type
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    # Use pandas excel reader which works with either xlrd or openpyxl
                    df = pd.read_excel(uploaded_file)
                
                # Preview the data
                st.write("Preview:")
                st.dataframe(df.head())
                
                # Confirm import
                if st.button("Import Users"):
                    try:
                        # Process the data
                        df = df.fillna("")
                        
                        # Handle time formats safely
                        try:
                            df["User Login Time"] = df["User Login Time"].apply(
                                lambda x: str(x) if pd.notna(x) else ""
                            )
                            df["User Logout Time"] = df["User Logout Time"].apply(
                                lambda x: str(x) if pd.notna(x) else ""
                            )
                        except Exception as e:
                            st.warning(f"Warning when processing time formats: {str(e)}")
                        
                        # Import to database
                        conn = get_db_connection()
                        if conn:
                            cursor = conn.cursor()
                            
                            users_updated = 0
                            users_created = 0
                            
                            for _, row in df.iterrows():
                                # Check if user exists
                                cursor.execute(
                                    """
                                    SELECT user_id FROM users 
                                    WHERE user_slack_id = ? OR user_email_id = ?
                                    """,
                                    (row.get("Slack ID", ""), row.get("User Email ID", "")),
                                )
                                user = cursor.fetchone()
                                user_id = user[0] if user else None
                                
                                if user:
                                    # Update existing user
                                    cursor.execute(
                                        """
                                        UPDATE users SET
                                            user_name = ?,
                                            user_email_id = ?,
                                            user_whatsapp_number = ?,
                                            user_login_time = ?,
                                            user_logout_time = ?,
                                            supervisor_name = ?,
                                            supervisor_email_id = ?,
                                            supervisor_slack_id = ?,
                                            supervisor_whatsapp_number = ?,
                                            second_supervisor_name = ?,
                                            second_supervisor_slack_id = ?,
                                            second_supervisor_email_id = ?
                                        WHERE user_id = ?
                                        """,
                                        (
                                            row.get("User Name", ""),
                                            str(row.get("User Email ID", "")),
                                            str(row.get("User WhatsApp Number", "")),
                                            row.get("User Login Time", ""),
                                            row.get("User Logout Time", ""),
                                            row.get("Supervisor Name", ""),
                                            row.get("Supervisor Email ID", ""),
                                            row.get("Supervisor Slack ID", ""),
                                            row.get("Supervisor WhatsApp Number", ""),
                                            row.get("Second Supervisor Name", ""),
                                            row.get("Second Supervisor Slack ID", ""),
                                            row.get("Second Supervisor Email ID", ""),
                                            user_id,
                                        ),
                                    )
                                    users_updated += 1
                                else:
                                    # Insert new user
                                    cursor.execute(
                                        """
                                        INSERT INTO users (
                                            user_slack_id, user_name, user_email_id, user_whatsapp_number,
                                            user_login_time, user_logout_time, supervisor_name,
                                            supervisor_email_id, supervisor_slack_id, supervisor_whatsapp_number,
                                            second_supervisor_name, second_supervisor_slack_id, second_supervisor_email_id
                                        )
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                        """,
                                        (
                                            row.get("Slack ID", ""),
                                            row.get("User Name", ""),
                                            str(row.get("User Email ID", "")),
                                            str(row.get("User WhatsApp Number", "")),
                                            row.get("User Login Time", ""),
                                            row.get("User Logout Time", ""),
                                            row.get("Supervisor Name", ""),
                                            row.get("Supervisor Email ID", ""),
                                            row.get("Supervisor Slack ID", ""),
                                            row.get("Supervisor WhatsApp Number", ""),
                                            row.get("Second Supervisor Name", ""),
                                            row.get("Second Supervisor Slack ID", ""),
                                            row.get("Second Supervisor Email ID", ""),
                                        ),
                                    )
                                    users_created += 1
                            
                            conn.commit()
                            conn.close()
                            
                            st.success(f"Import successful! Created {users_created} new users and updated {users_updated} existing users.")
                    except Exception as e:
                        st.error(f"Error importing data: {str(e)}")
            except Exception as e:
                st.error(f"Error reading file: {str(e)}")
        
        # Export all users to Excel
        st.markdown("### Export All Users")
        if st.button("Export All Users"):
            conn = get_db_connection()
            if conn:
                try:
                    df_all_users = pd.read_sql_query("SELECT * FROM users", conn)
                    conn.close()
                    
                    # Rename columns to match template
                    column_mapping = {
                        "user_id": "User ID",
                        "user_slack_id": "Slack ID",
                        "user_name": "User Name",
                        "user_email_id": "User Email ID",
                        "user_whatsapp_number": "User WhatsApp Number",
                        "user_login_time": "User Login Time",
                        "user_logout_time": "User Logout Time",
                        "supervisor_name": "Supervisor Name",
                        "supervisor_email_id": "Supervisor Email ID",
                        "supervisor_slack_id": "Supervisor Slack ID",
                        "supervisor_whatsapp_number": "Supervisor WhatsApp Number",
                        "second_supervisor_name": "Second Supervisor Name",
                        "second_supervisor_slack_id": "Second Supervisor Slack ID",
                        "second_supervisor_email_id": "Second Supervisor Email ID"
                    }
                    
                    df_all_users = df_all_users.rename(columns={k: v for k, v in column_mapping.items() if k in df_all_users.columns})
                    
                    # Export to file
                    export_data(df_all_users, f"all_users_{datetime.now().strftime('%Y%m%d')}")
                except Exception as e:
                    st.error(f"Error exporting users: {str(e)}")


# Attendance Records Page
elif page == "Attendance Records":
    st.header("Attendance Records")
    
    # Initialize variables at the page level
    view_type = "All Users"  # Default value
    selected_date = datetime.now()  # Default value
    
    # Date selection
    col1, col2 = st.columns(2)
    with col1:
        selected_date = st.date_input("Select Date", selected_date)
    with col2:
        view_type = st.radio("View", ["All Users", "Late Check-ins", "Missing Check-ins"])
    
    # Format date for query
    date_str = selected_date.strftime("%Y-%m-%d")
    
    # Get attendance records for selected date
    conn = get_db_connection()
    
    if conn:
        try:
            # Query to get all attendance records with user info
            query = """
            SELECT 
                u.user_id, u.user_name, u.user_login_time AS expected_login, 
                a.login_time AS actual_login, a.logout_time AS actual_logout,
                a.self_notified, a.supervisor_notified, a.second_supervisor_notified,
                a.is_supervisor_acknowledged, a.is_second_supervisor_acknowledged,
                a.email_supervisor_notified, a.email_second_supervisor_notified
            FROM users u
            LEFT JOIN audits a ON u.user_slack_id = a.user_slack_id AND a.workday = ?
            """
            
            # Apply filters based on view type
            if view_type == "Late Check-ins":
                query += " WHERE a.login_time IS NOT NULL"
            elif view_type == "Missing Check-ins":
                query += " WHERE a.login_time IS NULL"
            
            # Execute query
            df_attendance = pd.read_sql_query(query, conn, params=(date_str,))
            conn.close()
            
            # Process data for display
            if not df_attendance.empty:
                # Calculate lateness
                def calculate_status(row):
                    if pd.isna(row['actual_login']):
                        return "Missing"
                    
                    try:
                        # Extract times for comparison
                        if not row['expected_login'] or pd.isna(row['expected_login']):
                            return "No Expected Time"
                            
                        expected_time = datetime.strptime(f"{date_str} {row['expected_login']}", "%Y-%m-%d %H:%M")
                        
                        try:
                            actual_login = str(row['actual_login'])
                            if len(actual_login) > 16:  # Truncate if too long
                                actual_login = actual_login[:16]
                            actual_time = datetime.strptime(actual_login, "%Y-%m-%d %H:%M")
                            time_diff = actual_time - expected_time
                            minutes_late = time_diff.total_seconds() / 60
                            
                            if minutes_late > 5:
                                return f"Late ({int(minutes_late)} min)"
                            else:
                                return "On Time"
                        except:
                            return "Invalid Format"
                    except Exception as e:
                        return f"Error: {str(e)}"
                
                # Apply status calculation safely
                try:
                    df_attendance['status'] = df_attendance.apply(calculate_status, axis=1)
                except Exception as e:
                    st.error(f"Error calculating status: {str(e)}")
                    df_attendance['status'] = "Error"
                
                # Display attendance records
                st.subheader(f"Attendance Records for {date_str}")
                
                # Add metrics
                total_users = len(df_attendance)
                on_time = len(df_attendance[df_attendance['status'] == 'On Time'])
                late = len(df_attendance[df_attendance['status'].str.contains('Late', na=False)])
                missing = len(df_attendance[df_attendance['status'] == 'Missing'])
                
                # Create metrics
                metrics_col1, metrics_col2, metrics_col3, metrics_col4 = st.columns(4)
                metrics_col1.metric("Total Users", total_users)
                metrics_col2.metric("On Time", on_time)
                metrics_col3.metric("Late", late)
                metrics_col4.metric("Missing", missing)
                
                # Display table
                st.dataframe(
                    df_attendance[[
                        'user_name', 'expected_login', 'actual_login', 
                        'actual_logout', 'status'
                    ]].rename(columns={
                        'user_name': 'User Name',
                        'expected_login': 'Expected Login',
                        'actual_login': 'Actual Login',
                        'actual_logout': 'Actual Logout',
                        'status': 'Status'
                    }),
                    use_container_width=True
                )
                
                # Detail view for each user
                st.subheader("Detailed Records")
                for _, row in df_attendance.iterrows():
                    with st.expander(f"{row['user_name']} - {row['status']}"):
                        # Create columns for layout
                        detail_col1, detail_col2 = st.columns(2)
                        
                        # Column 1: Basic info
                        with detail_col1:
                            st.markdown(f"**Expected Login:** {row['expected_login']}")
                            st.markdown(f"**Actual Login:** {row['actual_login'] if not pd.isna(row['actual_login']) else 'Not logged in'}")
                            st.markdown(f"**Actual Logout:** {row['actual_logout'] if not pd.isna(row['actual_logout']) else 'Not logged out'}")
                        
                        # Column 2: Notification status
                        with detail_col2:
                            st.markdown(f"**Self Notifications:** {row['self_notified']}")
                            st.markdown(f"**Supervisor Notifications (Slack):** {row['supervisor_notified']}")
                            st.markdown(f"**Second Supervisor Notifications (Slack):** {row['second_supervisor_notified']}")
                            st.markdown(f"**Supervisor Notifications (Email):** {row.get('email_supervisor_notified', 0)}")
                            st.markdown(f"**Second Supervisor Notifications (Email):** {row.get('email_second_supervisor_notified', 0)}")
                            st.markdown(f"**Supervisor Acknowledged:** {'Yes' if row['is_supervisor_acknowledged'] else 'No'}")
                            st.markdown(f"**Second Supervisor Acknowledged:** {'Yes' if row['is_second_supervisor_acknowledged'] else 'No'}")
            else:
                st.info(f"No attendance records found for {date_str}")
        except Exception as e:
            st.error(f"Error loading attendance records: {str(e)}")
            if conn:
                conn.close()
    else:
        st.error("Failed to connect to database")

# Analytics Page
elif page == "Analytics":
    st.header("Attendance Analytics")
    
    # Date range selection
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", datetime.now() - timedelta(days=7))
    with col2:
        end_date = st.date_input("End Date", datetime.now())
    
    # Format dates for query
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    # Get analytics data
    conn = get_db_connection()
    
    if conn:
        try:
            # Query to get all attendance records within date range
            query = """
            SELECT 
                a.workday, u.user_name, u.user_login_time AS expected_login, 
                a.login_time AS actual_login, a.self_notified, 
                a.supervisor_notified, a.second_supervisor_notified
            FROM audits a
            JOIN users u ON a.user_slack_id = u.user_slack_id
            WHERE a.workday BETWEEN ? AND ?
            ORDER BY a.workday
            """
            
            # Execute query
            df_analytics = pd.read_sql_query(query, conn, params=(start_str, end_str))
            conn.close()
            
            if not df_analytics.empty:
                # Process data for analytics
                df_analytics['workday'] = pd.to_datetime(df_analytics['workday'])
                
                # Calculate on-time status
                def calculate_lateness(row):
                    if pd.isna(row['actual_login']):
                        return "Missing"
                    
                    try:
                        # Extract dates and times
                        if not row['expected_login'] or pd.isna(row['expected_login']):
                            return "No Expected Time"
                            
                        workday = row['workday'].strftime("%Y-%m-%d")
                        expected_time = datetime.strptime(f"{workday} {row['expected_login']}", "%Y-%m-%d %H:%M")
                        
                        try:
                            actual_login = str(row['actual_login'])
                            if len(actual_login) > 16:  # Truncate if too long
                                actual_login = actual_login[:16]
                            actual_time = datetime.strptime(actual_login, "%Y-%m-%d %H:%M")
                            
                            # Calculate time difference
                            time_diff = actual_time - expected_time
                            minutes_late = time_diff.total_seconds() / 60
                            
                            if minutes_late <= 0:
                                return "Early"
                            elif minutes_late <= 5:
                                return "On Time"
                            elif minutes_late <= 15:
                                return "Slightly Late"
                            elif minutes_late <= 30:
                                return "Late"
                            else:
                                return "Very Late"
                        except:
                            return "Invalid Format"
                    except Exception as e:
                        return "Error"
                
                # Apply status calculation safely
                try:
                    df_analytics['status'] = df_analytics.apply(calculate_lateness, axis=1)
                except Exception as e:
                    st.error(f"Error calculating status: {str(e)}")
                    df_analytics['status'] = "Error"
                
                # Tab selection for different charts
                tab1, tab2, tab3, tab4 = st.tabs(["Daily Summary", "User Performance", "Notification Stats",  "Weekly Work Hours"])
                
                # Tab 1: Daily Summary
                with tab1:
                    st.subheader("Daily Attendance Summary")
                    
                    # Group by day and status
                    daily_summary = df_analytics.groupby(['workday', 'status']).size().reset_index(name='count')
                    
                    # Pivot for stacked bar chart
                    daily_pivot = daily_summary.pivot(index='workday', columns='status', values='count').fillna(0)
                    
                    # Create stacked bar chart
                    try:
                        fig = px.bar(
                            daily_pivot, 
                            barmode='stack',
                            labels={"value": "Number of Users", "workday": "Date"},
                            height=500,
                            color_discrete_map={
                                'Early': '#28a745',
                                'On Time': '#4CAF50', 
                                'Slightly Late': '#FFC107', 
                                'Late': '#FF9800', 
                                'Very Late': '#F44336',
                                'Missing': '#6c757d',
                                'Error': '#999999',
                                'No Expected Time': '#333333'
                            }
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                    except Exception as e:
                        st.error(f"Error creating chart: {str(e)}")
                        st.dataframe(daily_pivot)
                    
                    # Summary metrics
                    st.subheader("Summary Metrics")
                    total_days = df_analytics['workday'].nunique()
                    total_records = len(df_analytics)
                    on_time_rate = len(df_analytics[df_analytics['status'].isin(['Early', 'On Time'])]) / total_records * 100 if total_records > 0 else 0
                    late_rate = len(df_analytics[df_analytics['status'].isin(['Slightly Late', 'Late', 'Very Late'])]) / total_records * 100 if total_records > 0 else 0
                    missing_rate = len(df_analytics[df_analytics['status'] == 'Missing']) / total_records * 100 if total_records > 0 else 0
                    
                    # Display metrics
                    metrics_col1, metrics_col2, metrics_col3, metrics_col4 = st.columns(4)
                    metrics_col1.metric("Total Days", total_days)
                    metrics_col2.metric("On Time %", f"{on_time_rate:.1f}%")
                    metrics_col3.metric("Late %", f"{late_rate:.1f}%")
                    metrics_col4.metric("Missing %", f"{missing_rate:.1f}%")
                
                # Tab 2: User Performance
                with tab2:
                    st.subheader("User Performance")
                    
                    # Group by user and status
                    user_summary = df_analytics.groupby(['user_name', 'status']).size().reset_index(name='count')
                    
                    # Get list of users for selection
                    users = df_analytics['user_name'].unique()
                    selected_user = st.selectbox("Select User", ["All Users"] + list(users))
                    
                    if selected_user == "All Users":
                        # Calculate performance for all users
                        user_performance = user_summary.pivot(index='user_name', columns='status', values='count').fillna(0)
                        
                        # Calculate total and on-time percentage
                        user_performance['Total'] = user_performance.sum(axis=1)
                        on_time_cols = ['Early', 'On Time'] if 'Early' in user_performance.columns and 'On Time' in user_performance.columns else []
                        if on_time_cols and 'Total' in user_performance.columns:
                            user_performance['On Time %'] = (user_performance[on_time_cols].sum(axis=1) / user_performance['Total'] * 100).round(1)
                        else:
                            user_performance['On Time %'] = 0
                        
                        # Sort by on-time percentage
                        try:
                            user_performance = user_performance.sort_values('On Time %', ascending=False)
                        except:
                            pass
                        
                        # Display table
                        st.dataframe(user_performance, use_container_width=True)
                        
                        # Create bar chart of user performance
                        try:
                            fig = px.bar(
                                user_performance.reset_index().sort_values('On Time %'),
                                x='user_name',
                                y='On Time %',
                                color='On Time %',
                                color_continuous_scale=['#F44336', '#FFC107', '#4CAF50'],
                                labels={"user_name": "User", "On Time %": "On Time Percentage"},
                                height=500
                            )
                            
                            st.plotly_chart(fig, use_container_width=True)
                        except Exception as e:
                            st.error(f"Error creating chart: {str(e)}")
                    else:
                        # Filter for selected user
                        user_data = df_analytics[df_analytics['user_name'] == selected_user]
                        
                        # Create daily status chart
                        user_daily = user_data.set_index('workday')['status']
                        
                        # Map status to numeric value for heatmap
                        status_map = {
                            'Early': 5,
                            'On Time': 4,
                            'Slightly Late': 3,
                            'Late': 2,
                            'Very Late': 1,
                            'Missing': 0,
                            'Error': -1,
                            'No Expected Time': -2
                        }
                        user_daily = user_daily.map(lambda x: status_map.get(x, -1))
                        
                        # Create calendar heatmap
                        calendar_data = []
                        for date, status in user_daily.items():
                            calendar_data.append({
                                'date': date.strftime('%Y-%m-%d'),
                                'status': status
                            })
                        
                        calendar_df = pd.DataFrame(calendar_data)
                        if not calendar_df.empty:
                            try:
                                calendar_df['date'] = pd.to_datetime(calendar_df['date'])
                                calendar_df['day'] = calendar_df['date'].dt.day_name()
                                calendar_df['week'] = calendar_df['date'].dt.isocalendar().week
                                calendar_df['month'] = calendar_df['date'].dt.month_name()
                                
                                try:
                                    fig = px.imshow(
                                        calendar_df.pivot(index='day', columns='date', values='status'),
                                        color_continuous_scale=[
                                            '#333333',  # Error
                                            '#6c757d',  # Missing
                                            '#F44336',  # Very Late
                                            '#FF9800',  # Late
                                            '#FFC107',  # Slightly Late
                                            '#4CAF50',  # On Time
                                            '#28a745'   # Early
                                        ],
                                        labels={"color": "Status"},
                                        height=300
                                    )
                                    
                                    fig.update_layout(
                                        xaxis_title="Date",
                                        yaxis_title="Day of Week"
                                    )
                                    
                                    st.plotly_chart(fig, use_container_width=True)
                                except Exception as e:
                                    st.error(f"Error creating heatmap: {str(e)}")
                                    st.dataframe(calendar_df)
                            except Exception as e:
                                st.error(f"Error processing calendar data: {str(e)}")
                        
                        # Summary stats for user
                        on_time_count = len(user_data[user_data['status'].isin(['Early', 'On Time'])])
                        late_count = len(user_data[user_data['status'].isin(['Slightly Late', 'Late', 'Very Late'])])
                        missing_count = len(user_data[user_data['status'] == 'Missing'])
                        total_count = len(user_data)
                        
                        # Display metrics
                        user_col1, user_col2, user_col3, user_col4 = st.columns(4)
                        user_col1.metric("Total Days", total_count)
                        user_col2.metric("On Time Days", on_time_count, f"{on_time_count/total_count*100:.1f}%" if total_count > 0 else "0.0%")
                        user_col3.metric("Late Days", late_count, f"{late_count/total_count*100:.1f}%" if total_count > 0 else "0.0%")
                        user_col4.metric("Missing Days", missing_count, f"{missing_count/total_count*100:.1f}%" if total_count > 0 else "0.0%")
                        
                        # Show detailed user data
                        st.dataframe(
                            user_data[['workday', 'expected_login', 'actual_login', 'status']].sort_values('workday', ascending=False),
                            use_container_width=True
                        )
                
                # Tab 3: Notification Stats
                with tab3:
                    st.subheader("Notification Statistics")
                    
                    # Calculate notification stats
                    df_analytics['notified'] = df_analytics['self_notified'] > 0
                    df_analytics['supervisor_escalated'] = df_analytics['supervisor_notified'] > 0
                    df_analytics['second_supervisor_escalated'] = df_analytics['second_supervisor_notified'] > 0
                    
                    # Daily notification counts
                    daily_notifications = df_analytics.groupby('workday').agg({
                        'notified': 'sum',
                        'supervisor_escalated': 'sum',
                        'second_supervisor_escalated': 'sum'
                    }).reset_index()
                    
                    # Rename columns for display
                    daily_notifications.columns = ['Date', 'User Notifications', 'Supervisor Escalations', 'Second Supervisor Escalations']
                    
                    # Create line chart
                    try:
                        fig = px.line(
                            daily_notifications,
                            x='Date',
                            y=['User Notifications', 'Supervisor Escalations', 'Second Supervisor Escalations'],
                            markers=True,
                            labels={"value": "Count", "variable": "Notification Type"},
                            height=400
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                    except Exception as e:
                        st.error(f"Error creating notification chart: {str(e)}")
                        st.dataframe(daily_notifications)
                    
                    # Calculate escalation rates
                    total_late = len(df_analytics[df_analytics['notified']])
                    supervisor_escalation_rate = len(df_analytics[df_analytics['supervisor_escalated']]) / total_late * 100 if total_late > 0 else 0
                    second_supervisor_escalation_rate = len(df_analytics[df_analytics['second_supervisor_escalated']]) / total_late * 100 if total_late > 0 else 0
                    
                    # Display metrics
                    notif_col1, notif_col2, notif_col3 = st.columns(3)
                    notif_col1.metric("Total Late/Missing Incidents", total_late)
                    notif_col2.metric("Supervisor Escalation Rate", f"{supervisor_escalation_rate:.1f}%")
                    notif_col3.metric("Second Supervisor Escalation Rate", f"{second_supervisor_escalation_rate:.1f}%")
                    
                    # Show notification counts by user
                    st.subheader("Notifications by User")
                    user_notifications = df_analytics.groupby('user_name').agg({
                        'self_notified': 'sum',
                        'supervisor_notified': 'sum',
                        'second_supervisor_notified': 'sum',
                        'workday': 'count'
                    }).reset_index()
                    
                    user_notifications.columns = ['User', 'Self Notifications', 'Supervisor Escalations', 'Second Supervisor Escalations', 'Total Days']
                    
                    # Sort by total notifications
                    user_notifications['Total Notifications'] = user_notifications['Self Notifications'] + user_notifications['Supervisor Escalations'] + user_notifications['Second Supervisor Escalations']
                    user_notifications = user_notifications.sort_values('Total Notifications', ascending=False)
                    
                    st.dataframe(user_notifications, use_container_width=True)
                    
                    # Create bar chart of users with most notifications
                    top_users = user_notifications.head(10)
                    
                    try:
                        fig = px.bar(
                            top_users,
                            x='User',
                            y=['Self Notifications', 'Supervisor Escalations', 'Second Supervisor Escalations'],
                            barmode='stack',
                            labels={"value": "Count", "variable": "Notification Type"},
                            height=400
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                    except Exception as e:
                        st.error(f"Error creating top users chart: {str(e)}")
            else:
                st.info(f"No attendance records found between {start_str} and {end_str}")
        except Exception as e:
            st.error(f"Error loading analytics: {str(e)}")
            if conn:
                conn.close()
    else:
        st.error("Failed to connect to database")

# Settings Page
elif page == "Settings":
    st.header("Settings")
    
    # Create tabs for different settings
    tab1, tab2, tab3 = st.tabs(["Notification Settings", "Holidays", "System Info"])
    
    # Tab 1: Notification Settings
    with tab1:
        st.subheader("Notification Settings")
        
        # Current settings from config
        try:
            import config
            
            current_self_notify = 3
            current_sup_escalation = config.SUPERVISOR_ESCALATION_MINUTES
            current_sup_interval = config.SUPERVISOR_NOTIFICATION_INTERVAL_MINUTES
            current_check_interval = config.SCHEDULER_CHECK_INTERVAL_MINUTES
        except:
            current_self_notify = 3
            current_sup_escalation = 2
            current_sup_interval = 30
            current_check_interval = 2
        
        with st.form("notification_settings"):
            # User notifications
            st.markdown("#### User Notifications")
            user_notify = st.number_input(
                "Number of user notifications before escalation",
                min_value=1,
                max_value=10,
                value=current_self_notify
            )
            
            # Supervisor escalation settings
            st.markdown("#### Supervisor Escalation")
            sup_escalation = st.number_input(
                "Minutes before escalating to second supervisor",
                min_value=1,
                max_value=60,
                value=current_sup_escalation
            )
            
            sup_interval = st.number_input(
                "Minimum minutes between supervisor notifications",
                min_value=1,
                max_value=60,
                value=current_sup_interval
            )
            
            # Check interval
            st.markdown("#### System Timing")
            check_interval = st.number_input(
                "Minutes between attendance checks",
                min_value=1,
                max_value=30,
                value=current_check_interval
            )
            
            # Submit button
            submit = st.form_submit_button("Save Settings")
            
            if submit:
                # Update config.py file
                try:
                    config_file_path = 'config.py'
                    if os.path.exists(config_file_path):
                        with open(config_file_path, 'r') as file:
                            config_content = file.read()
                        
                        # Replace config values
                        config_content = config_content.replace(
                            f"SUPERVISOR_ESCALATION_MINUTES = {current_sup_escalation}",
                            f"SUPERVISOR_ESCALATION_MINUTES = {sup_escalation}"
                        )
                        config_content = config_content.replace(
                            f"SUPERVISOR_NOTIFICATION_INTERVAL_MINUTES = {current_sup_interval}",
                            f"SUPERVISOR_NOTIFICATION_INTERVAL_MINUTES = {sup_interval}"
                        )
                        config_content = config_content.replace(
                            f"SCHEDULER_CHECK_INTERVAL_MINUTES = {current_check_interval}",
                            f"SCHEDULER_CHECK_INTERVAL_MINUTES = {check_interval}"
                        )
                        
                        # Write updated config
                        with open(config_file_path, 'w') as file:
                            file.write(config_content)
                        
                        # Update notification_service.py for user notification count
                        notification_file_path = 'notification_service.py'
                        if os.path.exists(notification_file_path):
                            with open(notification_file_path, 'r') as file:
                                service_content = file.read()
                            
                            # Replace user notification limit
                            service_content = service_content.replace(
                                f"if self_notified < 3:",
                                f"if self_notified < {user_notify}:"
                            )
                            
                            # Write updated service
                            with open(notification_file_path, 'w') as file:
                                file.write(service_content)
                            
                            st.success("Settings updated successfully! Please restart the bot for changes to take effect.")
                        else:
                            st.warning(f"File {notification_file_path} not found. Only config.py was updated.")
                    else:
                        st.error(f"Config file {config_file_path} not found.")
                except Exception as e:
                    st.error(f"Error updating settings: {str(e)}")
        
        # Add note about restarting
        st.info("Note: Changes to these settings require restarting the Slack Bot application to take effect.")
    
    # Tab 2: Holidays
    with tab2:
        st.subheader("Holiday Management")
        
        # Get current holidays from utils.py
        try:
            utils_file_path = 'utils.py'
            if os.path.exists(utils_file_path):
                with open(utils_file_path, 'r') as file:
                    utils_content = file.read()
                
                # Extract holidays list
                import re
                holidays_match = re.search(r'holidays = \[(.*?)\]', utils_content, re.DOTALL)
                
                if holidays_match:
                    holidays_content = holidays_match.group(1)
                    # Extract dates from the content
                    holiday_dates = re.findall(r'"([0-9]{4}-[0-9]{2}-[0-9]{2})"', holidays_content)
                else:
                    holiday_dates = []
                    st.warning("Could not find holidays list in utils.py.")
            else:
                holiday_dates = []
                st.error(f"Utils file {utils_file_path} not found.")
        except Exception as e:
            holiday_dates = []
            st.error(f"Error reading holidays: {str(e)}")
        
        # Convert to DataFrame for display
        holidays_df = pd.DataFrame({'date': holiday_dates})
        if not holidays_df.empty:
            holidays_df['date'] = pd.to_datetime(holidays_df['date'])
            holidays_df = holidays_df.sort_values('date')
        
        # Form to add new holiday
        with st.form("add_holiday"):
            new_holiday = st.date_input("Add Holiday", datetime.now())
            add_holiday = st.form_submit_button("Add Holiday")
            
            if add_holiday:
                new_holiday_str = new_holiday.strftime("%Y-%m-%d")
                if new_holiday_str in holiday_dates:
                    st.warning(f"{new_holiday_str} is already in the holidays list.")
                else:
                    try:
                        utils_file_path = 'utils.py'
                        if os.path.exists(utils_file_path):
                            with open(utils_file_path, 'r') as file:
                                utils_content = file.read()
                            
                            # Update utils.py file
                            new_holidays = holiday_dates + [new_holiday_str]
                            new_holidays.sort()
                            
                            # Format for writing to file
                            holidays_str = ',\n        '.join([f'"{date}"' for date in new_holidays])
                            
                            # Replace in file
                            import re
                            new_utils_content = re.sub(
                                r'holidays = \[(.*?)\]',
                                f'holidays = [\n        {holidays_str}\n    ]',
                                utils_content,
                                flags=re.DOTALL
                            )
                            
                            with open(utils_file_path, 'w') as file:
                                file.write(new_utils_content)
                            
                            st.success(f"Added {new_holiday_str} to holidays list.")
                            st.rerun()
                        else:
                            st.error(f"Utils file {utils_file_path} not found.")
                    except Exception as e:
                        st.error(f"Error adding holiday: {str(e)}")
        
        # Display current holidays
        st.subheader("Current Holidays")
        if not holidays_df.empty:
            for _, row in holidays_df.iterrows():
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**{row['date'].strftime('%Y-%m-%d')}** ({row['date'].strftime('%A')})")
                with col2:
                    if st.button("Remove", key=row['date'].strftime('%Y%m%d')):
                        try:
                            utils_file_path = 'utils.py'
                            if os.path.exists(utils_file_path):
                                with open(utils_file_path, 'r') as file:
                                    utils_content = file.read()
                                
                                # Remove from list
                                new_holidays = [d for d in holiday_dates if d != row['date'].strftime('%Y-%m-%d')]
                                
                                # Format for writing to file
                                holidays_str = ',\n        '.join([f'"{date}"' for date in new_holidays])
                                
                                # Replace in file
                                import re
                                new_utils_content = re.sub(
                                    r'holidays = \[(.*?)\]',
                                    f'holidays = [\n        {holidays_str}\n    ]',
                                    utils_content,
                                    flags=re.DOTALL
                                )
                                
                                with open(utils_file_path, 'w') as file:
                                    file.write(new_utils_content)
                                
                                st.success(f"Removed {row['date'].strftime('%Y-%m-%d')} from holidays list.")
                                st.rerun()
                            else:
                                st.error(f"Utils file {utils_file_path} not found.")
                        except Exception as e:
                            st.error(f"Error removing holiday: {str(e)}")
        else:
            st.info("No holidays configured.")
    
    # Tab 3: System Info
    with tab3:
        st.subheader("System Information")
        
        # Database status
        st.markdown("#### Database Status")
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                
                # Get table counts
                cursor.execute("SELECT COUNT(*) FROM users")
                users_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM audits")
                audits_count = cursor.fetchone()[0]
                
                # Get database file size
                db_size = os.path.getsize("logger.db") / (1024 * 1024)  # Convert to MB
                
                # Close connection
                conn.close()
                
                # Display info
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Users", users_count)
                col2.metric("Total Audit Records", audits_count)
                col3.metric("Database Size", f"{db_size:.2f} MB")
                
                st.success("Database is connected and operational.")
            else:
                st.error("Failed to connect to database")
        except Exception as e:
            st.error(f"Database error: {str(e)}")
        
        # Bot status
        st.markdown("#### Bot Status")
        try:
            import requests
            try:
                response = requests.get("http://localhost:8000/debug", timeout=2)
                if response.status_code == 200:
                    bot_status = response.json()
                    
                    # Display bot info
                    st.json(bot_status)
                    st.success("Bot is running.")
                else:
                    st.warning(f"Bot is not responding properly. Status code: {response.status_code}")
            except requests.exceptions.RequestException:
                st.error("Could not connect to bot. Make sure the bot is running.")
        except ImportError:
            st.error("Requests library not installed. Install with 'pip install requests'")
        
        # Create backup button
        if st.button("Create Database Backup"):
            try:
                db_file_path = "logger.db"
                if os.path.exists(db_file_path):
                    # Get current timestamp
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_filename = f"logger_backup_{timestamp}.db"
                    
                    # Copy database file
                    import shutil
                    shutil.copy2(db_file_path, backup_filename)
                    
                    # Create download link
                    with open(backup_filename, "rb") as file:
                        st.download_button(
                            label="Download Backup",
                            data=file,
                            file_name=backup_filename,
                            mime="application/octet-stream"
                        )
                    
                    st.success(f"Backup created: {backup_filename}")
                else:
                    st.error(f"Database file {db_file_path} not found.")
            except Exception as e:
                st.error(f"Error creating backup: {str(e)}")

# Add footer
st.markdown("---")
st.markdown("Slack Attendance Dashboard | Developed by Eminds | © 2025")