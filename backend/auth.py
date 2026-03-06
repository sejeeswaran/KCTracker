"""
Authentication module — manages the global auth.db.
Only stores login credentials. No ledger data here.
"""

import sqlite3
import bcrypt
from datetime import datetime
from config import AUTH_DB_PATH


def get_auth_db():
    """Get a connection to the authentication database."""
    conn = sqlite3.connect(AUTH_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_auth_db():
    """Create the users table in auth.db if it doesn't exist."""
    conn = get_auth_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def hash_password(password):
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password, password_hash):
    """Verify a password against its bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def register_user(username, password):
    """
    Register a new user.
    Returns (True, message) on success, (False, message) on failure.
    """
    conn = get_auth_db()
    cursor = conn.cursor()

    # Check if username already exists
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        conn.close()
        return False, "Username already exists."

    # Hash password
    pw_hash = hash_password(password)
    created_at = datetime.now().isoformat()

    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username, pw_hash, created_at),
        )
        conn.commit()
        conn.close()
        return True, "Registration successful."
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Username already exists."


def login_user(username, password):
    """
    Authenticate a user.
    Returns (True, user_dict) on success, (False, message) on failure.
    """
    conn = get_auth_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return False, "Invalid username or password."

    if verify_password(password, user["password_hash"]):
        return True, dict(user)

    return False, "Invalid username or password."
