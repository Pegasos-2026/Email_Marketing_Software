from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _get_fernet():
    key = getattr(settings, 'EMAIL_ENCRYPTION_KEY', None)
    if not key:
        raise ValueError(
            'EMAIL_ENCRYPTION_KEY is not configured. Add it to your .env file.'
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_value(value: str) -> str:
    if not value:
        return value
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt_value(value: str) -> str:
    if not value:
        return value
    try:
        return _get_fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        return value
