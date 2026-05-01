from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv

load_dotenv()

# يجب توليد مفتاح لمرة واحدة وحفظه في .env باسم ENCRYPTION_KEY
# لتوليده استخدم: Fernet.generate_key()
SECRET_KEY = os.getenv("ENCRYPTION_KEY").encode()
cipher_suite = Fernet(SECRET_KEY)

def encrypt_key(plain_text: str) -> str:
    """تشفير النص (API Key)"""
    if not plain_text: return None
    return cipher_suite.encrypt(plain_text.encode()).decode()

def decrypt_key(encrypted_text: str) -> str:
    """فك تشفير النص (API Key) عند التنفيذ"""
    if not encrypted_text: return None
    return cipher_suite.decrypt(encrypted_text.encode()).decode()
