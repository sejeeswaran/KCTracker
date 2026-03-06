"""
Sync module: bridges app.py to sync_manager.py.
Provides refresh_drive_data() for the /sync route.
"""

from backend.sync_manager import sync_all, sync_download_on_login, sync_upload_after_change


def refresh_drive_data(username):
    """
    Full sync with Google Drive.
    Called by the /sync route.
    """
    return sync_all(username)
