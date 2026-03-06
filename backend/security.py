"""
Security module: Fernet encryption for bank statement passwords.
The encryption key is stored locally in config.py — never on Google Drive.
"""

from cryptography.fernet import Fernet
from config import ENCRYPTION_KEY


def _get_fernet():
    """Get a Fernet instance using the configured encryption key."""
    return Fernet(ENCRYPTION_KEY)


def encrypt_password(password):
    """Encrypt a plaintext password. Returns an encrypted string."""
    f = _get_fernet()
    return f.encrypt(password.encode("utf-8")).decode("utf-8")


def decrypt_password(encrypted_password):
    """Decrypt an encrypted password. Returns the plaintext string."""
    f = _get_fernet()
    return f.decrypt(encrypted_password.encode("utf-8")).decode("utf-8")
