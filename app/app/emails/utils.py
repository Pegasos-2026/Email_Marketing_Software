from cryptography.fernet import Fernet
from django.conf import settings
fernet=Fernet(settings.EMAIL_ENCRYPTION_KEY.encode())
def encrypt_value(value:str)->str:
    return fernet.encrypt(value.encode()).decode()
def decrypt_value(value:str)->str:
    return fernet.decrypt(value.encode()).decode()
